"""Overlap recomputation helpers for competitor-to-lead matching."""

from __future__ import annotations

import json
from typing import Any, Dict, List


async def recompute_single_competitor_overlap(*, conn, competitor: Dict[str, Any]) -> List[str]:
    leads = await conn.fetch("SELECT lead_id, company FROM leads WHERE company IS NOT NULL")
    if not leads:
        return []

    lead_name_to_id: Dict[str, str] = {}
    for lead in leads:
        name = (lead["company"] or "").lower().strip()
        if name:
            lead_name_to_id[name] = str(lead["lead_id"])

    overlap_ids: List[str] = []
    companies_table = competitor.get("companies_table") or []
    if isinstance(companies_table, str):
        try:
            companies_table = json.loads(companies_table)
        except Exception:
            companies_table = []
    if isinstance(companies_table, list):
        for entry in companies_table:
            cust_name = (entry.get("company_name") or entry.get("name") or "").lower().strip()
            if cust_name:
                lead_id = lead_name_to_id.get(cust_name)
                if lead_id and lead_id not in overlap_ids:
                    overlap_ids.append(lead_id)

    for cust_name in (competitor.get("customer_companies") or []):
        lead_id = lead_name_to_id.get(cust_name.lower().strip())
        if lead_id and lead_id not in overlap_ids:
            overlap_ids.append(lead_id)

    for aka in (competitor.get("also_known_names") or []):
        lead_id = lead_name_to_id.get(aka.lower().strip())
        if lead_id and lead_id not in overlap_ids:
            overlap_ids.append(lead_id)

    return overlap_ids


async def compute_competitor_overlap(*, conn, logger) -> None:
    try:
        leads = await conn.fetch("SELECT lead_id, company FROM leads WHERE company IS NOT NULL")
        if not leads:
            logger.info("[Competitors] No leads in tenant DB to compute overlap")
            return

        lead_name_to_id: Dict[str, str] = {}
        for lead in leads:
            name = (lead["company"] or "").lower().strip()
            if name:
                lead_name_to_id[name] = str(lead["lead_id"])

        competitors = await conn.fetch(
            "SELECT supplier_slug, supplier_name, customer_companies, also_known_names, companies_table FROM bol_competitors"
        )

        for comp in competitors:
            overlap_ids: List[str] = []
            comp_slug = comp["supplier_slug"]
            companies_table = comp["companies_table"]
            if isinstance(companies_table, str):
                try:
                    companies_table = json.loads(companies_table)
                except Exception:
                    companies_table = None

            if isinstance(companies_table, list) and companies_table:
                for entry in companies_table:
                    cust_name = (entry.get("company_name") or entry.get("name") or "").lower().strip()
                    if cust_name:
                        lead_id = lead_name_to_id.get(cust_name)
                        if lead_id and lead_id not in overlap_ids:
                            overlap_ids.append(lead_id)
            else:
                for cust_name in (comp["customer_companies"] or []):
                    lead_id = lead_name_to_id.get(cust_name.lower().strip())
                    if lead_id and lead_id not in overlap_ids:
                        overlap_ids.append(lead_id)

            for aka in (comp["also_known_names"] or []):
                lead_id = lead_name_to_id.get(aka.lower().strip())
                if lead_id and lead_id not in overlap_ids:
                    overlap_ids.append(lead_id)

            await conn.execute(
                """
                UPDATE bol_competitors
                SET overlap_count = $1,
                    overlap_buyer_slugs = $2,
                    last_updated_at = NOW()
                WHERE supplier_slug = $3
                """,
                len(overlap_ids),
                overlap_ids,
                comp_slug,
            )

        from .threat import compute_threat_levels
        await compute_threat_levels(conn=conn)

        logger.info(f"[Competitors] Overlap + threat computed for {len(competitors)} competitors against {len(leads)} leads")
    except Exception as e:
        logger.error(f"[Competitors] Overlap computation failed: {e}", exc_info=True)
