"""
Signal Evaluation Agent — LLM-based customer signal analysis.

Analyzes interaction history (emails, deal room views, calls, meetings) and
determines buying signal level, label, urgency score, and reasoning.

Processes customers in batches of 5 for token efficiency.
Runs as a scheduled Temporal job (daily at 3 AM UTC), NOT on page load.

Signal levels (most → least urgent):
  RED    — Immediate action required (quote requests, pricing questions, urgent replies)
  PURPLE — High intent (deal room views, high-confidence intent emails)
  GREEN  — Early buying signals (MOQ, lead time, sample keywords, email opens)
  NONE   — Dormant, no meaningful signal in 30 days; or explicit rejection
           ("Not interested" label auto-marks linked leads as not_interested)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.core.model_factory import ModelFactory

logger = logging.getLogger(__name__)


class SignalEvaluationAgent:
    """LLM-powered buying signal evaluator for CRM customers."""

    BATCH_SIZE = 5  # customers per LLM call

    # Canonical labels grouped by signal level — used to snap LLM output
    LABELS_BY_LEVEL: Dict[str, List[str]] = {
        "red": ["Respond now", "Quote requested", "Pricing question"],
        "purple": [
            "Replied today", "High intent", "Deal room viewed",
            "Viewed multiple times",
        ],
        "green": [
            "Asking about MOQ", "Asking about lead time",
            "Asking about samples", "Import spike", "Reorder window",
            "Early research", "Buyer interested", "Buyer objection",
            "Buyer question", "Shared internally", "Opened",
            "Clicked email",
        ],
        "none": ["Not interested"],
    }

    def __init__(
        self,
        provider: str = "openai",
        model_name: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Signal Evaluation Agent",
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key,
        )
        model_info = self.model_factory.get_model_info()
        self.provider = model_info.provider
        self.model_name = model_info.model_name
        self.client = model_info.client
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def evaluate_signals_for_tenant(self, conn) -> Dict[str, Any]:
        """
        Main entry point. Evaluates signals for all active customers in a tenant.

        1. Pre-filter: only customers with activity in last 30 days
        2. Gather interaction data per customer
        3. Batch into groups of BATCH_SIZE, send to LLM
        4. Persist results to clients
        5. Clear stale signals for inactive customers
        """
        total = await conn.fetchval("SELECT COUNT(*) FROM clients")

        # 1. Pre-filter
        active_ids = await self._get_active_customers(conn)
        self.logger.info(
            f"Signal evaluation: {len(active_ids)} active / {total} total customers"
        )

        if not active_ids:
            cleared = await self._clear_stale_signals(conn, [])
            return {
                "evaluated": 0,
                "cleared": cleared,
                "skipped_inactive": total,
            }

        # 2. Gather data
        customer_data = await self._gather_interaction_data(conn, active_ids)

        # 3. Process in batches
        results: List[Dict] = []
        for i in range(0, len(customer_data), self.BATCH_SIZE):
            batch = customer_data[i : i + self.BATCH_SIZE]
            self.logger.info(
                f"Evaluating batch {i // self.BATCH_SIZE + 1} "
                f"({len(batch)} customers)"
            )
            batch_results = await self._evaluate_batch(batch)
            results.extend(batch_results)

        # 4. Persist
        await self._persist_signals(conn, results)

        # 5. Auto-qualify leads whose CRM signal is "Deal room viewed"
        qualified = await self._qualify_leads_for_deal_room_views(conn, results)

        # 6. Auto-mark leads as not_interested when signal is "Not interested"
        not_interested = await self._mark_leads_not_interested(conn, results)

        # 7. Clear stale
        cleared = await self._clear_stale_signals(conn, active_ids)

        return {
            "evaluated": len(results),
            "cleared": cleared,
            "qualified_leads": qualified,
            "not_interested_leads": not_interested,
            "skipped_inactive": total - len(active_ids),
        }

    # ------------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------------

    async def _get_active_customers(self, conn) -> List[int]:
        """Customer IDs with any interaction in the last 30 days."""
        rows = await conn.fetch("""
            SELECT DISTINCT client_id FROM (
                SELECT customer_id AS client_id FROM crm_emails
                WHERE created_at >= NOW() - INTERVAL '30 days'
                UNION
                SELECT d.client_id FROM deals d
                JOIN deal_room_views drv ON d.deal_id = drv.deal_id
                WHERE drv.started_at >= NOW() - INTERVAL '30 days'
                UNION
                SELECT customer_id AS client_id FROM interaction_details
                WHERE created_at >= NOW() - INTERVAL '30 days'
            ) active
        """)
        return [r["client_id"] for r in rows]

    async def _gather_interaction_data(
        self, conn, client_ids: List[int]
    ) -> List[Dict]:
        """Gather interaction history per customer for LLM input."""
        results = []
        for client_id in client_ids:
            info = await conn.fetchrow(
                "SELECT ci.client_id, ci.name AS company_name, "
                "p_primary.full_name AS contact_name, "
                "ci.stage, ci.signal "
                "FROM clients ci "
                "LEFT JOIN LATERAL ("
                "  SELECT full_name FROM personnel "
                "  WHERE client_id = ci.client_id AND is_primary = true LIMIT 1"
                ") p_primary ON true "
                "WHERE ci.client_id = $1",
                client_id,
            )
            if not info:
                continue

            emails = await conn.fetch(
                """
                SELECT direction, subject, body, intent,
                       created_at, opened_at
                FROM crm_emails
                WHERE customer_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC LIMIT 20
            """,
                client_id,
            )

            deals = await conn.fetch(
                """
                SELECT d.room_status, d.view_count, d.last_viewed_at,
                       d.created_at AS deal_created_at
                FROM deals d WHERE d.client_id = $1
                ORDER BY d.created_at DESC LIMIT 5
            """,
                client_id,
            )

            interactions = await conn.fetch(
                """
                SELECT type, content, source, created_at
                FROM interaction_details
                WHERE customer_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC LIMIT 10
            """,
                client_id,
            )

            previous_signal = info["signal"]
            previous_level = previous_signal.get("level") if isinstance(previous_signal, dict) else None

            results.append(
                {
                    "client_id": client_id,
                    "company_name": info["company_name"],
                    "contact_name": info["contact_name"],
                    "stage": info["stage"],
                    "previous_signal": previous_level,
                    "emails": [dict(e) for e in emails],
                    "deals": [dict(d) for d in deals],
                    "interactions": [dict(i) for i in interactions],
                }
            )
        return results

    # ------------------------------------------------------------------
    # LLM evaluation
    # ------------------------------------------------------------------

    async def _evaluate_batch(self, batch: List[Dict]) -> List[Dict]:
        """Send batch of customers to LLM for signal evaluation."""
        prompt = self._build_prompt(batch)
        system_message = self._get_system_message()
        response = self.model_factory.generate_content(prompt, system_message)
        return self._parse_response(response, batch)

    def _get_system_message(self) -> str:
        return (
            "You are a B2B sales signal analyst. You evaluate customer interaction "
            "history and determine buying signal levels.\n\n"
            "Signal levels (most to least urgent):\n"
            "- RED: Immediate action required. Customer actively requesting quotes, "
            "asking pricing, expressing urgent needs, strong intent to buy NOW. "
            "Response within hours matters.\n"
            "- PURPLE: High intent. Customer viewing deal rooms, engaging with "
            "multiple emails, evaluating options. Response within 1-2 days.\n"
            "- GREEN: Early buying signals. Customer mentioned MOQ, lead times, "
            "samples, or buying keywords. Also moderate engagement like email "
            "opens, clicks, or shared content. Early research phase.\n"
            "- NONE: No meaningful buying signal in last 30 days. Dormant or "
            "not engaged. IMPORTANT: If customer explicitly said 'not interested', "
            "'no thank you', 'we chose another supplier', or similar rejection, "
            "still use NONE level but set signal_label to exactly "
            "'Not interested'.\n\n"
            "IMPORTANT RULES:\n"
            '- Analyze CONTENT and TONE, not just counts.\n'
            '- "not interested" reply is NOT red — use NONE with label '
            '"Not interested". "can you send pricing?" IS red.\n'
            "- Multiple deal room views in short period = strong purple "
            "(active evaluation).\n"
            "- Consider recency: quote request from 25 days ago < quote request "
            "from today.\n"
            "- Previous signal context matters: red → quiet might mean lost to "
            "competitor (none) or still deciding (green).\n\n"
            "Return EXACTLY one JSON array with one object per customer. "
            "No markdown, no extra text."
        )

    def _build_prompt(self, batch: List[Dict]) -> str:
        sections = []
        for customer in batch:
            section = (
                f"\n--- CUSTOMER: {customer['company_name']} "
                f"(ID: {customer['client_id']}) ---\n"
            )
            section += f"Contact: {customer['contact_name']}\n"
            section += f"Current Stage: {customer['stage']}\n"
            section += f"Previous Signal: {customer['previous_signal'] or 'none'}\n"

            # Format emails
            if customer["emails"]:
                section += "\nEMAIL HISTORY (most recent first):\n"
                for e in customer["emails"][:10]:
                    direction = (
                        "→ SENT" if e["direction"] == "sent" else "← RECEIVED"
                    )
                    date = (
                        e["created_at"].strftime("%Y-%m-%d")
                        if e["created_at"]
                        else "?"
                    )
                    opened = " [OPENED]" if e.get("opened_at") else ""
                    intent = (
                        f" [intent: {e['intent']}]" if e.get("intent") else ""
                    )
                    body_preview = (e.get("body") or "")[:300]
                    section += (
                        f"  {date} {direction}{opened}{intent}: "
                        f"{e.get('subject', '(no subject)')}\n"
                    )
                    if body_preview:
                        section += f"    Body: {body_preview}\n"
            else:
                section += "\nNo emails in last 30 days.\n"

            # Format deals
            if customer["deals"]:
                section += "\nDEAL ROOM ACTIVITY:\n"
                for d in customer["deals"]:
                    views = d.get("view_count", 0)
                    status = d.get("room_status", "unknown")
                    last_view = (
                        d["last_viewed_at"].strftime("%Y-%m-%d")
                        if d.get("last_viewed_at")
                        else "never"
                    )
                    section += (
                        f"  Status: {status}, Views: {views}, "
                        f"Last viewed: {last_view}\n"
                    )

            # Format other interactions
            if customer["interactions"]:
                section += "\nOTHER INTERACTIONS:\n"
                for i in customer["interactions"]:
                    date = (
                        i["created_at"].strftime("%Y-%m-%d")
                        if i["created_at"]
                        else "?"
                    )
                    section += (
                        f"  {date} [{i['type']}] "
                        f"{(i.get('content') or '')[:200]}\n"
                    )

            sections.append(section)

        prompt = "Evaluate the buying signal for each customer below.\n\n"
        prompt += "For each customer, return:\n"
        prompt += (
            '{"client_id": <int>, "signal_level": "red|purple|orange|green|none", '
            '"signal_label": "<one of the allowed labels below>", '
            '"urgency_score": <0-100>, '
            '"reasoning": "<1-2 sentence explanation>"}\n\n'
        )
        prompt += (
            "ALLOWED signal_label values (use EXACTLY one of these, no variations):\n"
            "  RED:    Respond now | Quote requested | Pricing question\n"
            "  PURPLE: Replied today | High intent | Deal room viewed | Viewed multiple times\n"
            "  GREEN:  Asking about MOQ | Asking about lead time | Asking about samples | "
            "Import spike | Reorder window | Early research | "
            "Buyer interested | Buyer objection | Buyer question | "
            "Shared internally | Opened | Clicked email\n"
            "  NONE:   Not interested\n\n"
        )
        prompt += "Return a JSON array with exactly one entry per customer.\n"
        prompt += "\n".join(sections)
        return prompt

    def _parse_response(self, response: str, batch: List[Dict]) -> List[Dict]:
        """Parse LLM JSON response. Falls back to previous signal on error."""
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            results = json.loads(text)
            if not isinstance(results, list):
                results = [results]
        except json.JSONDecodeError:
            self.logger.error(
                f"Failed to parse LLM signal response: {text[:500]}"
            )
            return [
                {
                    "client_id": c["client_id"],
                    "signal_level": c.get("previous_signal"),
                    "signal_label": None,
                    "urgency_score": None,
                    "reasoning": "LLM parse error — kept previous signal",
                }
                for c in batch
            ]

        valid_levels = {"red", "purple", "green", "none"}
        all_canonical = {
            lbl.lower(): lbl
            for labels in self.LABELS_BY_LEVEL.values()
            for lbl in labels
        }
        for r in results:
            level = r.get("signal_level")
            # Remap orange → green (orange level was removed)
            if level == "orange":
                level = "green"
                r["signal_level"] = "green"
            if level not in valid_levels:
                r["signal_level"] = None
                level = None

            # Snap label to canonical form within the result's level
            label = r.get("signal_label")
            if label and level:
                lower = label.lower()
                if lower in all_canonical:
                    # Exact match — normalize casing
                    r["signal_label"] = all_canonical[lower]
                else:
                    # Fuzzy: pick best from same-level candidates
                    candidates = self.LABELS_BY_LEVEL.get(level, [])
                    best = self._match_label(label, candidates)
                    if best:
                        self.logger.info(
                            f"Snapped label '{label}' → '{best}' "
                            f"for client {r.get('client_id')}"
                        )
                        r["signal_label"] = best
                    else:
                        # Fall back to first label for this level
                        r["signal_label"] = candidates[0] if candidates else label

            # Preserve "none" level for "Not interested" so it gets persisted
            if r.get("signal_level") == "none":
                if (r.get("signal_label") or "").lower() != "not interested":
                    r["signal_level"] = None

            if r.get("urgency_score") is not None:
                try:
                    r["urgency_score"] = max(0, min(100, int(r["urgency_score"])))
                except (ValueError, TypeError):
                    r["urgency_score"] = None

        return results

    @staticmethod
    def _match_label(label: str, candidates: List[str]) -> Optional[str]:
        """Pick the best candidate label using keyword overlap, level-scoped."""
        if not candidates:
            return None
        # Extract meaningful words (skip short filler words)
        filler = {"a", "an", "the", "and", "or", "with", "in", "of", "for", "to", "is", "once", "active"}
        label_words = {w for w in label.lower().split() if w not in filler and len(w) > 1}
        best_score = 0
        best = None
        for candidate in candidates:
            candidate_words = {w for w in candidate.lower().split() if w not in filler and len(w) > 1}
            overlap = len(label_words & candidate_words)
            if overlap > best_score:
                best_score = overlap
                best = candidate
        return best if best_score > 0 else None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _persist_signals(self, conn, results: List[Dict]) -> None:
        """Write signal evaluation results to clients.signal JSONB."""
        now = datetime.now(timezone.utc).isoformat()
        for r in results:
            # Pass dict directly — the pool's JSONB codec handles json.dumps()
            signal_data = {
                "level": r.get("signal_level"),
                "label": r.get("signal_label"),
                "reasoning": r.get("reasoning"),
                "urgency_score": r.get("urgency_score"),
                "evaluated_at": now,
            }
            await conn.execute(
                "UPDATE clients SET signal = $1 "
                "WHERE client_id = $2",
                signal_data,
                r["client_id"],
            )

    async def _qualify_leads_for_deal_room_views(
        self, conn, results: List[Dict]
    ) -> int:
        """When signal is 'Deal room viewed', set the linked lead status to 'qualified'."""
        deal_room_client_ids = [
            r["client_id"]
            for r in results
            if r.get("signal_label") == "Deal room viewed"
        ]
        if not deal_room_client_ids:
            return 0

        result = await conn.execute(
            "UPDATE leads SET status = 'qualified', updated_at = NOW() "
            "WHERE lead_id IN ("
            "  SELECT DISTINCT lead_id FROM personnel "
            "  WHERE client_id = ANY($1::int[]) AND lead_id IS NOT NULL"
            ") AND status != 'qualified'",
            deal_room_client_ids,
        )
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError, AttributeError):
            count = 0

        if count:
            self.logger.info(
                f"Auto-qualified {count} lead(s) from deal room views "
                f"(client_ids: {deal_room_client_ids})"
            )
        return count

    async def _mark_leads_not_interested(
        self, conn, results: List[Dict]
    ) -> int:
        """When signal is 'Not interested', set the linked lead status to 'not_interested'."""
        not_interested_client_ids = [
            r["client_id"]
            for r in results
            if (r.get("signal_label") or "").lower() == "not interested"
        ]
        if not not_interested_client_ids:
            return 0

        result = await conn.execute(
            "UPDATE leads SET status = 'not_interested', updated_at = NOW() "
            "WHERE lead_id IN ("
            "  SELECT DISTINCT lead_id FROM personnel "
            "  WHERE client_id = ANY($1::int[]) AND lead_id IS NOT NULL"
            ") AND status != 'not_interested'",
            not_interested_client_ids,
        )
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError, AttributeError):
            count = 0

        if count:
            self.logger.info(
                f"Auto-marked {count} lead(s) as not_interested "
                f"(client_ids: {not_interested_client_ids})"
            )
        return count

    async def _clear_stale_signals(
        self, conn, active_ids: List[int]
    ) -> int:
        """Clear signals for customers with no activity in 30 days."""
        if active_ids:
            result = await conn.execute(
                "UPDATE clients SET signal = NULL "
                "WHERE client_id NOT IN (SELECT unnest($1::int[])) "
                "AND signal IS NOT NULL",
                active_ids,
            )
        else:
            result = await conn.execute(
                "UPDATE clients SET signal = NULL "
                "WHERE signal IS NOT NULL"
            )
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError, AttributeError):
            return 0
