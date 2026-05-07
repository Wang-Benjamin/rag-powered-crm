"""Trade-specific prompt utilities for cross-cultural email generation.

Used by both CRM and Leadgen prompt builders when email_type is a trade type
or when the user's input contains Chinese characters.
"""

from typing import Optional, List

from email_core.models import TRADE_EMAIL_TYPES


def _contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return any('\u4e00' <= c <= '\u9fff' for c in text)


def needs_cultural_adaptation(
    email_type: Optional[str] = None,
    custom_prompt: Optional[str] = None,
) -> bool:
    """Determine if cross-cultural adaptation should be applied.

    Triggers on either:
    1. email_type is a trade type (initial_outreach, rfq_response, etc.)
    2. custom_prompt contains Chinese characters
    """
    if email_type and email_type in TRADE_EMAIL_TYPES:
        return True
    if custom_prompt and _contains_chinese(custom_prompt):
        return True
    return False


CULTURAL_ADAPTATION_PROMPT = """
CROSS-CULTURAL ADAPTATION:
You are adapting communication for a manufacturer reaching a North American buyer.
1. Generate entirely in professional North American business English
2. Transform Chinese business norms to Western B2B style
3. Replace superlatives ("best quality", "top manufacturer") with concrete data (specs, certifications)
4. Do NOT translate literally — adapt tone, structure, and cultural conventions
5. Preserve all specific data points (prices, quantities, specs) exactly
"""


def build_trade_context(
    products: Optional[list] = None,
    fob_price: Optional[str] = None,
    fob_price_old: Optional[str] = None,
    certifications: Optional[List[str]] = None,
    moq: Optional[str] = None,
    lead_time: Optional[str] = None,
    sample_status: Optional[str] = None,
    effective_date: Optional[str] = None,
) -> str:
    """Build trade-specific context section for the email generation prompt.

    Returns empty string if no trade fields are provided.
    """
    sections = []

    # New: structured products list
    if products:
        valid = [p for p in products if isinstance(p, dict) and (p.get("name") or p.get("fobPrice") or p.get("fob_price") or p.get("landedPrice") or p.get("landed_price"))]
        if valid:
            lines = []
            for p in valid:
                name = p.get("name", "")
                fob = p.get("fobPrice") or p.get("fob_price", "")
                landed = p.get("landedPrice") or p.get("landed_price", "")
                parts = []
                if fob:
                    parts.append(f"FOB {fob}")
                if landed:
                    parts.append(f"Landed {landed}")
                pricing = ", ".join(parts)
                if name and pricing:
                    lines.append(f"- {name}: {pricing}")
                elif name:
                    lines.append(f"- {name}")
                elif pricing:
                    lines.append(f"- {pricing}")
            if lines:
                sections.append("Products & Pricing:\n" + "\n".join(lines))

    # Legacy: single fob_price field
    if not products:
        if fob_price and fob_price_old:
            sections.append(f"FOB Price: {fob_price_old} → {fob_price}")
        elif fob_price:
            sections.append(f"FOB Price: {fob_price}")

    if certifications:
        sections.append(f"Certifications: {', '.join(certifications)}")

    if moq:
        sections.append(f"Minimum Order Quantity: {moq}")

    if lead_time:
        sections.append(f"Lead Time: {lead_time}")

    if sample_status:
        sections.append(f"Sample Status: {sample_status}")

    if effective_date:
        sections.append(f"Effective Date: {effective_date}")

    if not sections:
        return ""

    return (
        "\n\nMANUFACTURER PRODUCT & PRICING DATA (include in email):\n"
        + "\n".join(sections)
        + "\n\nIMPORTANT: You MUST mention specific products and pricing (FOB and/or Landed prices) in the email body. "
        "The buyer needs to see concrete pricing to take the email seriously. "
        "If both FOB and Landed prices are provided, include both — Landed price shows total cost clarity.\n"
    )


BUYER_INTELLIGENCE_RULES = """
RULES FOR USING BUYER INTELLIGENCE — TONE IS CRITICAL:

1. BE RESPECTFUL AND HELPFUL, NOT CONFRONTATIONAL
   - You are offering value, not exposing vulnerabilities
   - Never say "your supplier is down X%" — that's aggressive
   - Instead, position yourself as a knowledgeable industry peer offering to help

2. USE DATA SUBTLY TO SHOW MARKET KNOWLEDGE
   - Good: "We work with several lighting importers in the Southeast US and noticed the market has been shifting. If you're exploring additional sourcing options, we'd love to share what we can offer."
   - Good: "Given your import volume in the lighting space, our pricing might be competitive — happy to share a quote."
   - Bad: "Your primary supplier dropped 89% — you need a new one." (confrontational)
   - Bad: "I see you haven't imported in 313 days" (surveillance tone)

3. LEAD WITH YOUR VALUE, USE DATA AS CONTEXT
   - The email should primarily be about what YOU offer (products, pricing, certifications)
   - BoL data provides context for WHY you're reaching out (timing, relevance)
   - The buyer should think "this is relevant to me" not "they're watching my shipments"

4. REFERENCE PATTERNS, NOT EXACT NUMBERS
   - Good: "active importers in your category", "companies with similar volume"
   - OK to use approximate ranges: "given your scale of operations"
   - Avoid: exact container counts, exact days since last shipment, exact YoY percentages

5. DO NOT NAME SPECIFIC SUPPLIERS
   - Never mention the buyer's supplier names
   - OK: "if any of your current sources are experiencing delays"
"""


def build_buyer_intelligence_context(buyer_intelligence: Optional[dict] = None) -> str:
    """Build buyer intelligence section from BoL data for email generation prompt.

    Expects structured output from bol_intelligence_builder.build_bol_intelligence().
    """
    if not buyer_intelligence or not buyer_intelligence.get('hasData'):
        return ""

    sections = []

    # Compose summary (top-line for quick context)
    compose_summary = buyer_intelligence.get('composeSummary')
    if compose_summary:
        sections.append(f"OVERVIEW: {compose_summary}")

    # Personalization angle
    pers = buyer_intelligence.get('personalization')
    if pers:
        parts = []
        if pers.get('annualShipments'):
            parts.append(f"~{pers['annualShipments']} shipments/yr")
        if pers.get('productCategories'):
            parts.append(f"Products: {', '.join(pers['productCategories'][:3])}")
        if pers.get('hsCodes'):
            parts.append(f"HS codes: {', '.join(pers['hsCodes'][:3])}")
        if pers.get('ports'):
            parts.append(f"Ports: {', '.join(pers['ports'][:3])}")
        if parts:
            sections.append("IMPORT PROFILE:\n" + "\n".join(f"- {p}" for p in parts))

    # Timing angle
    timing = buyer_intelligence.get('timing')
    if timing:
        parts = []
        if timing.get('daysSinceLastShipment') is not None:
            parts.append(f"Days since last shipment: {timing['daysSinceLastShipment']}")
        if timing.get('avgOrderCycleDays'):
            parts.append(f"Average reorder cycle: {timing['avgOrderCycleDays']} days")
        if timing.get('cyclePct') is not None:
            parts.append(f"Cycle progress: {timing['cyclePct']}%")
        if timing.get('reorderWindow'):
            parts.append(f"Reorder window: {timing['reorderWindow'].upper()}")
        if parts:
            sections.append("TIMING:\n" + "\n".join(f"- {p}" for p in parts))

    # Pricing angle
    pricing = buyer_intelligence.get('pricing')
    if pricing:
        parts = []
        if pricing.get('weightKgPerShipment'):
            parts.append(f"Weight per shipment: ~{pricing['weightKgPerShipment']:,.0f} kg")
        if pricing.get('teuPerShipment'):
            parts.append(f"TEU per shipment: {pricing['teuPerShipment']:.1f}")
        if parts:
            sections.append("SHIPMENT SIZE (use to frame pricing):\n" + "\n".join(f"- {p}" for p in parts))

    # Supplier vulnerability angle
    vuln = buyer_intelligence.get('supplierVulnerability')
    if vuln:
        parts = []
        primary = vuln.get('primarySupplier', {})
        if primary.get('share'):
            trend_str = ""
            if primary.get('trend') and primary['trend'] < -10:
                trend_str = f", down {abs(round(primary['trend']))}% YoY"
            parts.append(f"Primary CN supplier: {primary['share']:.0f}% share{trend_str}")
        if vuln.get('decliningSuppliers', 0) > 0:
            parts.append(f"Declining suppliers: {vuln['decliningSuppliers']} of {vuln.get('totalChineseSuppliers', '?')}")
        if parts:
            sections.append("SUPPLIER VULNERABILITY:\n" + "\n".join(f"- {p}" for p in parts))

    if not sections:
        return ""

    return (
        "\n════════════════════════════════════════════════════════════════\n"
        "BUYER INTELLIGENCE (from Bill of Lading data)\n"
        "════════════════════════════════════════════════════════════════\n\n"
        + "\n\n".join(sections)
        + "\n\n"
        + BUYER_INTELLIGENCE_RULES
        + "\n════════════════════════════════════════════════════════════════\n\n"
    )
