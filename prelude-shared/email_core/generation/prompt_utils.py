"""Shared prompt utilities for agentic email generation.

Used by both Leadgen and CRM prompt builders. These functions build compact
XML-tagged sections that feed into the classify-then-generate structured output.
"""

from datetime import datetime, timezone
from typing import List, Optional


def build_situational_context(email_history: list, lead_status: str) -> str:
    """Auto-determine relationship state from email history.

    Returns a compact <situation> block describing:
    - Relationship stage (first contact vs. ongoing)
    - Email count and last interaction timing
    - Last interaction summary + sentiment (if any)
    """
    if not email_history:
        return "<situation>\nRelationship: first contact (no prior emails)\n</situation>"

    total = len(email_history)

    # Find most recent email
    latest = email_history[0]  # Assume sorted newest-first
    last_date = latest.get('created_at') or latest.get('email_timestamp')
    last_direction = (latest.get('direction', 'sent')).lower()
    last_subject = latest.get('subject', '')

    # Calculate days since last interaction
    days_ago = ""
    if last_date:
        if isinstance(last_date, str):
            try:
                parsed = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                delta = datetime.now(timezone.utc) - parsed
                days_ago = f", {delta.days} days ago"
            except (ValueError, TypeError):
                pass
        elif hasattr(last_date, 'strftime'):
            delta = datetime.now(timezone.utc) - last_date.replace(tzinfo=timezone.utc) if last_date.tzinfo is None else datetime.now(timezone.utc) - last_date
            days_ago = f", {delta.days} days ago"

    # Determine sentiment of last email if it was received
    last_sentiment = ""
    if last_direction == 'received':
        body = (latest.get('body') or '')[:200]
        last_sentiment = f"\nLast reply snippet: {body}" if body else ""

    lines = [
        f"Relationship: {total} emails exchanged",
        f"Last interaction: {last_direction}{days_ago} | {last_subject}",
    ]
    if last_sentiment:
        lines.append(last_sentiment)

    return "<situation>\n" + "\n".join(lines) + "\n</situation>"


def build_buyer_signals(buyer_intelligence: Optional[dict]) -> str:
    """Flatten buyer_intelligence to top signals as a compact <buyer_signals> block.

    Instead of the nested 4-angle structure, extract the most actionable
    signals for the LLM: fit score, reorder timing, volume, ports, supplier
    dynamics. Returns empty string if no data.
    """
    if not buyer_intelligence or not buyer_intelligence.get('hasData'):
        return ""

    signals = []

    # Timing signals
    timing = buyer_intelligence.get('timing')
    if timing:
        cycle_pct = timing.get('cyclePct')
        avg_cycle = timing.get('avgOrderCycleDays')
        if cycle_pct is not None and avg_cycle:
            signals.append(f"Reorder timing: {cycle_pct}% through {avg_cycle}-day cycle")
        days_since = timing.get('daysSinceLastShipment')
        if days_since is not None:
            signals.append(f"Days since last shipment: {days_since}")

    # Volume / category signals
    pers = buyer_intelligence.get('personalization')
    if pers:
        annual = pers.get('annualShipments')
        if annual:
            signals.append(f"Import volume: ~{annual} shipments/yr")
        ports = pers.get('ports')
        if ports:
            signals.append(f"Ports: {', '.join(ports[:3])}")
        categories = pers.get('productCategories')
        if categories:
            signals.append(f"Categories: {', '.join(categories[:3])}")

    # Supplier vulnerability signals
    vuln = buyer_intelligence.get('supplierVulnerability')
    if vuln:
        primary = vuln.get('primarySupplier', {})
        if primary.get('share'):
            trend_str = ""
            if primary.get('trend') and primary['trend'] < -10:
                trend_str = f", declining {abs(round(primary['trend']))}% YoY"
            signals.append(f"Primary CN supplier: {primary['share']:.0f}% share{trend_str}")
    else:
        # Honest signal: don't let the model invent supplier claims when we have no data.
        signals.append("Supplier mix and recent activity not enriched — do not infer supplier vulnerability or timing")

    # Compose summary
    compose_summary = buyer_intelligence.get('composeSummary')
    if compose_summary:
        signals.insert(0, compose_summary)

    if not signals:
        return ""

    return "<buyer_signals>\n" + "\n".join(f"- {s}" for s in signals) + "\n</buyer_signals>"


def build_writing_style_instructions(writing_style: Optional[dict]) -> str:
    """Format writing style for system prompt injection.

    Returns a compact <writing_style> block. If no writing_style is provided,
    returns empty string (caller should use trade voice preset as fallback).
    """
    if not writing_style:
        return ""

    traits_list = "\n".join(f"- {trait}" for trait in writing_style.get('notableTraits', []))
    examples_list = "\n".join(f'- "{ex}"' for ex in writing_style.get('examples', []))

    return f"""<writing_style>
Length: {writing_style.get('typicalLength', 'N/A')}
Formality: {writing_style.get('formality', 'N/A')}
Greeting: {writing_style.get('commonGreeting', 'N/A')}
Traits:
{traits_list}
Examples:
{examples_list}
</writing_style>

Match this writing style exactly. Use their length, formality, greeting, traits, and phrasing."""


def format_thread_summary(email_history: list, max_verbatim: int = 5) -> str:
    """Format email history: last N verbatim, older ones as a 1-line summary.

    Args:
        email_history: List of email dicts, newest first.
        max_verbatim: Number of recent emails to include verbatim.

    Returns:
        Formatted string for <email_history> section, or message if empty.
    """
    if not email_history:
        return "No previous emails."

    verbatim = email_history[:max_verbatim]
    older = email_history[max_verbatim:]

    lines = []

    # Verbatim recent emails
    for email in verbatim:
        date = email.get('created_at') or email.get('email_timestamp', 'Unknown')
        if hasattr(date, 'strftime'):
            date = date.strftime("%Y-%m-%d")
        direction = (email.get('direction', 'sent')).upper()
        subject = email.get('subject', '')
        body = email.get('body', '')
        lines.append(f"[{date}] {direction}: {subject}\n{body}")

    # Summarize older emails
    if older:
        sent_count = sum(1 for e in older if (e.get('direction', 'sent')).lower() == 'sent')
        received_count = len(older) - sent_count
        lines.append(f"[...{len(older)} older emails: {sent_count} sent, {received_count} received]")

    return "\n\n".join(lines)
