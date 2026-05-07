"""Batched outreach-email generator for the two-pager Page 2.

Uses Anthropic (claude-haiku-4-5) to produce all 3 emails in a single call.
Keeps emails short (1 paragraph, ~50 words) so Page 2 fits in one A4.

Public contract:

    async def generate_outreach_emails(
        top3_buyers_with_contacts: list[dict],
        subject: str,
    ) -> dict[str, dict[str, str]]

Input buyers MUST carry: slug, name, city, state, annual_volume_tons,
trend_yoy_pct, cn_prev_supplier_count, cn_curr_supplier_count, cn_subheader,
contact_name, contact_title. Output: {buyer_slug: {"subject": str, "body": str}}
for every buyer with a name. On total LLM failure, every slug maps to a
fallback email so callers can still render Page 2.

Validation: any hallucinated $/date/cert in the body is replaced with
`[verify details]` — we never ground-truth-checked those in the prompt.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

from anthropic import APIError, AsyncAnthropic
from pydantic import BaseModel, ValidationError
from service_core.llm_json import extract_json

logger = logging.getLogger(__name__)

_client: Optional[AsyncAnthropic] = None

MODEL = "claude-sonnet-4-6"
CATEGORY_MODEL = "claude-sonnet-4-6"
TOTAL_TIMEOUT_SECS = 45.0
MAX_TOKENS = 1500


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _client = AsyncAnthropic(api_key=api_key, timeout=60.0)
    return _client


SYSTEM_PROMPT = """You write short, professional B2B outreach emails that Chinese suppliers send to US importers. The reader is a US decision-maker; the email is in English.

Hard rules:
- Return ONLY valid JSON matching the exact shape the user asks for. No prose, no markdown fences.
- Each email body is 1 SHORT paragraph, under 50 words total. No line breaks inside the body. No bullet lists. No "Dear Sir/Madam".
- Subject: write a natural email subject a real supplier would send — short (under 55 chars), sentence case, specific to the buyer when possible. Do NOT include raw HS codes (e.g. "9505.10"). Do NOT use the "<Category> — <value prop>" em-dash template. Avoid marketing slogans, ALL CAPS, and taglines. Think quick, human openers like "Quick intro from a {category} factory", "Potential backup supplier for {Company}", or "{FirstName} — {category} sourcing". Vary wording across the three buyers.
- Open with the contact's first name, then one sentence grounded in the buyer's data (CN supplier change, YoY trend, category). Do NOT invent data.
- KEEP these placeholders literal, exactly: [product category], $X.XX, MOQ [X] units. The sender fills them in later.
- Do NOT invent dollar amounts, dates, certifications, or product specs.
- End with ONE low-friction ask: spec sheet, samples, or a 15-min call. Not all three.
- Do not mention Prelude, Apollo, or any tooling. Write as the supplier.
- Email-address generation: if a buyer entry carries `synth_email_needed: true`, ALSO include an `email` field in that buyer's JSON output, formatted as a plausible corporate email like "alex@verka.com". Local part = lowercase first name only (no dots, no last name). Domain = derived from the company name: strip legal suffixes (Inc, LLC, Corp, Co., Ltd, LP) and generic qualifiers (International, Group, USA, US, Global) from the END only, lowercase, concatenate the remaining 1-2 brand words, append ".com". Examples: "Verka Food International" + Alex → alex@verkafood.com; "QVC Inc" + Jordan → jordan@qvc.com; "Joyful Trade" + Sam → sam@joyfultrade.com. AVOID @gmail.com / @yahoo.com / @hotmail.com, .net / .org / .io. If `synth_email_needed: false` (or absent), OMIT the `email` field entirely — do not overwrite real contacts."""


class _BuyerEmail(BaseModel):
    subject: str
    body: str
    # Only emitted when the buyer's input row carries `synth_email_needed: true`.
    # Real Apollo contacts already have a verified email — we never overwrite.
    email: Optional[str] = None


def _first_name(full_name: Optional[str]) -> str:
    if not full_name:
        return "there"
    return full_name.strip().split()[0]


def _supplier_delta_str(prev: int, curr: int) -> str:
    if prev == 0 and curr == 0:
        return "no CN supplier activity recorded"
    if prev == curr:
        return f"steady at {curr} CN suppliers"
    if curr < prev:
        return f"consolidated from {prev} CN suppliers to {curr}"
    return f"expanded from {prev} CN suppliers to {curr}"


def _volume_str(tons: Optional[float]) -> str:
    if not tons or tons <= 0:
        return "unknown"
    if tons >= 1_000:
        return f"~{tons / 1_000:.1f}kt/yr"
    return f"~{tons:.0f}t/yr"


def _build_user_prompt(top3: List[Dict[str, Any]], subject: str) -> str:
    slug_order = [b.get("slug") for b in top3 if b.get("slug")]
    buyer_lines: List[str] = []
    for b in top3:
        slug = b.get("slug") or ""
        name = b.get("name") or "Unknown"
        city = b.get("city") or ""
        state = b.get("state") or ""
        loc = ", ".join(x for x in (city, state) if x) or "USA"
        vol = _volume_str(b.get("annual_volume_tons"))
        trend = b.get("trend_yoy_pct")
        trend_str = f"{trend:+.1f}% YoY" if isinstance(trend, (int, float)) else "YoY unknown"
        delta = _supplier_delta_str(
            int(b.get("cn_prev_supplier_count") or 0),
            int(b.get("cn_curr_supplier_count") or 0),
        )
        contact_first = _first_name(b.get("contact_name"))
        contact_title = b.get("contact_title") or "decision-maker"
        subheader = b.get("cn_subheader") or ""
        synth_email_needed = bool(b.get("synth_email_needed"))
        buyer_lines.append(
            f"- slug: {slug}\n"
            f"  company: {name} ({loc})\n"
            f"  category: {subject}\n"
            f"  annual_volume: {vol}\n"
            f"  trend: {trend_str}\n"
            f"  cn_supplier_change: {delta}\n"
            f"  supply_chain_signal: {subheader}\n"
            f"  contact_first_name: {contact_first}\n"
            f"  contact_title: {contact_title}\n"
            f"  synth_email_needed: {str(synth_email_needed).lower()}"
        )
    buyers_block = "\n".join(buyer_lines)
    return (
        f"Generate an outreach email for EACH of the {len(top3)} buyers below. "
        f'Return JSON of the exact shape: {{"emails": {{"<buyer_slug>": '
        f'{{"subject": "...", "body": "...", "email": "<only when synth_email_needed=true>"}}}}}} '
        f"with one entry for every slug listed: {slug_order}. The `email` field "
        f"MUST appear when synth_email_needed is true and MUST be omitted when false.\n\n"
        f"Category: {subject}\n\nBuyers:\n{buyers_block}\n\n"
        "Remember: under 50 words per body, 1 single paragraph (no line breaks), keep [product category], $X.XX, MOQ [X] units literal. JSON only."
    )


_SAFE_DOLLAR_PLACEHOLDER = "$X.XX"
_DOLLAR_AMOUNT_RE = re.compile(r"\$[0-9][0-9,]*\.[0-9]{1,2}")
_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.IGNORECASE,
)
_CERT_RE = re.compile(
    r"\b(ISO\s?9001|ISO\s?14001|FDA[-\s]?registered|CE[-\s]?certified|"
    r"REACH[-\s]?compliant|BSCI|SEDEX|OEKO-?TEX)\b",
    re.IGNORECASE,
)


def _validate_email_body(body: str) -> str:
    if not body:
        return body

    def _strip_dollar(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0) == _SAFE_DOLLAR_PLACEHOLDER else "[verify details]"

    cleaned = _DOLLAR_AMOUNT_RE.sub(_strip_dollar, body)
    cleaned = _DATE_RE.sub("[verify details]", cleaned)
    cleaned = _CERT_RE.sub("[verify details]", cleaned)
    return cleaned


def _fallback_email(buyer: Dict[str, Any], subject: str) -> Dict[str, str]:
    first = _first_name(buyer.get("contact_name"))
    company = buyer.get("name")
    # Keep the fallback subject natural (no raw HS codes / template dashes) so
    # it matches the LLM subject style when generation fails.
    fallback_subject = (
        f"Potential backup supplier for {company}" if company else "Quick intro from a CN factory"
    )
    body = (
        f"Hi {first}, I came across {company or 'your team'} while mapping US importers "
        f"of [product category] and wanted to introduce our factory as a potential backup supplier — "
        f"we can ship [product category] at $X.XX with MOQ [X] units and flexible lead times. "
        f"Happy to share a spec sheet if useful — would a brief call next week make sense?"
    )
    return {"subject": fallback_subject, "body": body}


async def _single_call(
    system_prompt: str, user_prompt: str, timeout: float
) -> Optional[Dict[str, Dict[str, str]]]:
    try:
        client = _get_client()
        response = await asyncio.wait_for(
            client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("[TwoPager/email] Anthropic timed out")
        return None
    except APIError as e:
        logger.error(f"[TwoPager/email] Anthropic APIError: {e}")
        return None
    except Exception as e:
        logger.error(f"[TwoPager/email] Anthropic call failed: {e}")
        return None

    raw_text = ""
    for block in response.content or []:
        if getattr(block, "type", None) == "text":
            raw_text += getattr(block, "text", "")

    payload = extract_json(raw_text)
    if not isinstance(payload, dict):
        logger.warning("[TwoPager/email] no JSON object in Anthropic response")
        return None

    emails = payload.get("emails")
    if not isinstance(emails, dict):
        return None

    validated: Dict[str, Dict[str, str]] = {}
    for slug, val in emails.items():
        try:
            obj = _BuyerEmail(**val) if isinstance(val, dict) else None
        except ValidationError:
            continue
        if obj is None:
            continue
        entry: Dict[str, str] = {"subject": obj.subject, "body": obj.body}
        if obj.email:
            entry["email"] = obj.email
        validated[slug] = entry
    return validated


async def generate_outreach_emails(
    top3_buyers_with_contacts: List[Dict[str, Any]],
    subject: str,
) -> Dict[str, Dict[str, str]]:
    buyers = [b for b in (top3_buyers_with_contacts or []) if b.get("slug")]
    if not buyers:
        return {}

    user_prompt = _build_user_prompt(buyers, subject)
    expected_slugs = {b["slug"] for b in buyers}

    first = await _single_call(SYSTEM_PROMPT, user_prompt, timeout=TOTAL_TIMEOUT_SECS)
    emails: Dict[str, Dict[str, str]] = {
        slug: val for slug, val in (first or {}).items() if slug in expected_slugs
    }

    if 0 < len(emails) < len(expected_slugs):
        missing = expected_slugs - set(emails)
        logger.warning(
            f"[TwoPager/email] got {len(emails)}/{len(expected_slugs)}; retrying for {missing}"
        )
        retry_prompt = (
            user_prompt
            + f"\n\nCRITICAL: return exactly {len(expected_slugs)} emails, one per slug: {sorted(expected_slugs)}."
        )
        second = await _single_call(SYSTEM_PROMPT, retry_prompt, timeout=TOTAL_TIMEOUT_SECS)
        for slug, val in (second or {}).items():
            if slug in expected_slugs and slug not in emails:
                emails[slug] = val

    out: Dict[str, Dict[str, str]] = {}
    for buyer in buyers:
        slug = buyer["slug"]
        generated = emails.get(slug)
        if generated and generated.get("subject") and generated.get("body"):
            entry = {
                "subject": generated["subject"].strip(),
                "body": _validate_email_body(generated["body"].strip()),
            }
            # Preserve LLM-generated synth corporate email when present.
            gen_email = generated.get("email")
            if gen_email and isinstance(gen_email, str) and "@" in gen_email:
                entry["email"] = gen_email.strip().lower()
            out[slug] = entry
        else:
            logger.warning(f"[TwoPager/email] fallback for {slug}")
            out[slug] = _fallback_email(buyer, subject)

    return out


# ─── Combined location cleanup + supplier-change fabrication via Sonnet ──

_NORMALIZE_SYSTEM = """You clean US importer buyer data for a sales report.

For each buyer input, return:
1. city + state. Produce a clean US HQ city (2-40 chars, no street fragments,
   no "2Nd Fl", no "Suite 717", no "Po Box 393", no road names) and a
   2-letter US state code. If the raw city already looks clean, keep it.
   Never return null — if you genuinely don't know, pick a plausible US city
   for that company name.
2. cn_prev + cn_curr (integers). If BOTH raw_cn_prev and raw_cn_curr are 0,
   invent plausible integers (each in 2..15, with a non-zero difference)
   for a typical US importer of the given category. Otherwise pass through
   the raw values unchanged — do NOT overwrite real data.

Return JSON only."""


_TITLE_SYSTEM = """You generate bilingual report titles for US-importer market reports aimed at Chinese suppliers.

Given an HS code and/or a product description, return a short category-specific title in BOTH Chinese and English. The title names the product category the report covers.

Rules:
- CN title: 5-10 Chinese characters, concise, no punctuation, no "报告" / "买家" / "美国" framing words — just the product category (e.g. "LED灯具", "户外家具", "锂电池组", "开关电器").
- EN title: 2-5 words in Title Case, just the product category (e.g. "LED Lighting", "Outdoor Furniture", "Lithium Battery Packs").
- Do NOT include the HS code, "Importers", "Buyers", or "Report" in either title.
- Return ONLY valid JSON. No prose, no fences."""


async def generate_category_title(
    hs_code: Optional[str],
    product_description: Optional[str],
    timeout: float = 10.0,
) -> Dict[str, Optional[str]]:
    """Generate a bilingual {title_cn, title_en} for the report header.

    Uses Claude Haiku for latency. Returns {"title_cn": None, "title_en": None}
    on any failure — callers should fall back to the raw HS code / product
    description when either side is missing.
    """
    if not hs_code and not product_description:
        return {"title_cn": None, "title_en": None}

    user = (
        f"HS code: {hs_code or 'none'}\n"
        f"Product description: {product_description or 'none'}\n\n"
        'Return JSON of exact shape: {"title_cn": "...", "title_en": "..."}.'
    )
    try:
        client = _get_client()
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=_TITLE_SYSTEM,
                messages=[{"role": "user", "content": user}],
            ),
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"[TwoPager/title] AI title generation failed: {e}")
        return {"title_cn": None, "title_en": None}

    raw_text = ""
    for block in response.content or []:
        if getattr(block, "type", None) == "text":
            raw_text += getattr(block, "text", "")
    payload = extract_json(raw_text)
    if not isinstance(payload, dict):
        return {"title_cn": None, "title_en": None}

    cn = payload.get("title_cn")
    en = payload.get("title_en")
    return {
        "title_cn": cn.strip() if isinstance(cn, str) and cn.strip() else None,
        "title_en": en.strip() if isinstance(en, str) and en.strip() else None,
    }


async def normalize_and_fabricate_buyer_fields(
    buyers: List[Dict[str, Any]],
    hs_category: str,
    timeout: float = 25.0,
) -> Dict[str, Dict[str, Any]]:
    """Single Sonnet pass over all buyers: clean weird locations and
    fabricate supplier-change counts when real data is (0, 0).

    Input items need: slug, name, city, state, cn_prev, cn_curr.
    Returns {slug: {"city", "state", "cn_prev", "cn_curr"}}. Empty dict
    on any failure. Caller is responsible for applying the patches.
    """
    targets = [b for b in buyers if b.get("slug") and b.get("name")]
    if not targets:
        return {}

    lines: List[str] = []
    for b in targets:
        lines.append(
            f"- slug={b['slug']} name={b['name']} "
            f"raw_city={b.get('city') or 'none'} "
            f"raw_state={b.get('state') or 'none'} "
            f"raw_cn_prev={b.get('cn_prev', 0)} "
            f"raw_cn_curr={b.get('cn_curr', 0)}"
        )
    user = (
        f"HS category: {hs_category}\n\nBuyers:\n"
        + "\n".join(lines)
        + "\n\nReturn JSON of exact shape: "
        '{"buyers": {"<slug>": {"city": "...", "state": "XX", "cn_prev": N, "cn_curr": M}}}.'
    )

    try:
        client = _get_client()
        response = await asyncio.wait_for(
            client.messages.create(
                model=CATEGORY_MODEL,
                max_tokens=1800,
                system=_NORMALIZE_SYSTEM,
                messages=[{"role": "user", "content": user}],
            ),
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"[TwoPager/normalize] failed: {e}")
        return {}

    raw_text = ""
    for block in response.content or []:
        if getattr(block, "type", None) == "text":
            raw_text += getattr(block, "text", "")
    payload = extract_json(raw_text)
    if not isinstance(payload, dict):
        return {}
    buyers_block = payload.get("buyers")
    if not isinstance(buyers_block, dict):
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for slug, val in buyers_block.items():
        if not isinstance(val, dict):
            continue
        entry: Dict[str, Any] = {}
        city = val.get("city")
        if isinstance(city, str) and city.strip():
            entry["city"] = city.strip()
        state = val.get("state")
        if isinstance(state, str) and state.strip():
            entry["state"] = state.strip().upper()[:2]
        try:
            entry["cn_prev"] = int(val.get("cn_prev", 0))
            entry["cn_curr"] = int(val.get("cn_curr", 0))
        except (TypeError, ValueError):
            entry["cn_prev"] = 0
            entry["cn_curr"] = 0
        out[str(slug)] = entry
    logger.info(f"[TwoPager/normalize] normalized {len(out)}/{len(targets)} buyer fields")
    return out


# Hardcoded regex blocklist — applied BEFORE the Haiku classifier so the
# obvious cases (Amazon subsidiaries, "freight" / "logistics" in the name,
# known Chinese/Korean/Japanese brand US arms) are always rejected even if
# Haiku gets cautious. Word-boundary anchors avoid most false positives.
_HARD_BLOCKLIST_PATTERNS = [
    # Big-box / marketplace / retail majors
    r"\bamazon\b",
    r"\bwalmart\b",
    r"\bcostco\b",
    r"\bhome depot\b",
    r"\blowe'?s\b",
    r"\bbest buy\b",
    r"\bikea\b",
    r"\bwayfair\b",
    r"\bdollar (tree|general)\b",
    r"\bkohl'?s\b",
    r"\bmacy'?s\b",
    r"\bsam'?s club\b",
    r"\bmenards\b",
    r"\bstaples inc\b",
    r"\boffice depot\b",
    r"\btjx\b",
    r"\bross stores\b",
    r"\bkroger\b",
    r"\bcvs health\b",
    r"\bwalgreens\b",
    r"\bnordstrom\b",
    r"\bmacy\b",
    r"\bjcpenney\b",
    # Logistics / freight / 3PL
    r"\bfreight\b",
    r"\blogistics\b",
    r"\bforwarding\b",
    r"\bforwarder\b",
    r"\bcustoms broker\b",
    r"\b3pl\b",
    r"\bfulfillment\b",
    r"\bwarehousing\b",
    # Chinese brand US arms
    r"\bmidea\b",
    r"\bhaier\b",
    r"\bhisense\b",
    r"\blenovo\b",
    r"\bhuawei\b",
    r"\bxiaomi\b",
    r"\bbyd\b",
    r"\banker\b",
    r"\bshein\b",
    r"\btemu\b",
    r"\balibaba\b",
    r"\bbytedance\b",
    r"\btiktok\b",
    r"\bhikvision\b",
    r"\bdji\b",
    # Korean / Japanese majors with US operations
    r"\blg electronics\b",
    r"\blg sourcing\b",
    r"\bsamsung\b",
    r"\bsony\b",
    r"\bpanasonic\b",
    # Freight/logistics keywords
    r"\btransport(ation)?\b",
    r"\bcargo\b",
    r"\bshipping\b",
    r"\bconsolidation\b",
    r"\bsupply chain\b",
    r"\bcontainer\b",
    r"\bbrokerage\b",
    # Named offenders from Ben's QA
    r"\bprime agency\b",
    r"\bkerry apex\b",
    r"\basf global\b",
    r"\bcity ocean international\b",
    r"\bbestline supply chain\b",
    r"\blaufer group( international)?\b",
    r"\b(o[ .]?e[ .]?c|oec) shipping\b",
    r"\bde well container shipping\b",
    r"\boaks cargo\b",
    r"\bdhy shipping line\b",
    r"\bcrimsonlogic( us)?\b",
    r"\bjarvis international freight\b",
    r"\bforest shipping usa\b",
    r"\btopocean\b",
    r"\bhecny\b",
    r"\btanera\b",
    r"\bsun track\b",
    r"\bglobal etrade services\b",
]
_HARD_BLOCKLIST_RE = re.compile(
    "|".join(_HARD_BLOCKLIST_PATTERNS), re.IGNORECASE,
)


def _hard_blocklist_slugs(companies: List[Dict[str, Any]]) -> set[str]:
    """Return slugs whose `name` matches the hardcoded blocklist regex."""
    skip: set[str] = set()
    for c in companies:
        slug = c.get("slug")
        name = c.get("name") or ""
        if slug and _HARD_BLOCKLIST_RE.search(name):
            skip.add(str(slug))
    return skip


# Notify-party blocklist: reuses the full buyer-name blocklist patterns plus
# notify-specific forwarder names observed in Ben's QA review.
_NOTIFY_BLOCKLIST_PATTERNS = _HARD_BLOCKLIST_PATTERNS + [
    r"\byqn logistics\b",
    r"\bbama global\b",
    r"\bjaak transport\b",
    r"\bjkmy logistics\b",
    r"\bgrace container\b",
    r"\bfin whale\b",
    r"\beastern network express\b",
    r"\bmeitong\b",
    r"\bmorepro\b",
    r"\bexpeditors international\b",
    r"\bmohawk global\b",
    r"\bflexeco overseas\b",
    r"\bk trans worldwide\b",
]
_NOTIFY_BLOCKLIST_RE = re.compile(
    "|".join(_NOTIFY_BLOCKLIST_PATTERNS), re.IGNORECASE,
)


def _notify_party_forwarder_slugs(companies: List[Dict[str, Any]]) -> set[str]:
    """Return slugs where any notify-party string matches the notify blocklist.

    Checks the `Top Notify Parties` field (a string or list of strings).
    """
    skip: set[str] = set()
    for c in companies:
        slug = c.get("slug")
        if not slug:
            continue
        notify = c.get("Top Notify Parties") or c.get("top_notify_parties") or ""
        if isinstance(notify, list):
            notify = " ".join(str(n) for n in notify)
        if notify and _NOTIFY_BLOCKLIST_RE.search(str(notify)):
            skip.add(str(slug))
    return skip


# Transliterated-Chinese-name regex: anchored at start of company name.
# Catches Chinese shell consignees that pass concentration filters because
# they import 100% from CN (e.g. "Shenzhenshi Heveboik", "Hong Kong Jude").
_TRANSLITERATED_CHINESE_RE = re.compile(
    r"^(shenzhen\w*|hk|hongkong|hong kong|xiamen|fuzhou|fujian|zhengzhou|"
    r"nanjing|yantai|changsha|putian|guangzhou|hangzhou|ningbo|shanghai|"
    r"beijing|chongqing|qingdao|jinan|wuhan|chengdu|suzhou|shen zhen)\s+",
    re.IGNORECASE,
)


def _transliterated_chinese_slugs(companies: List[Dict[str, Any]]) -> set[str]:
    """Return slugs where the buyer name starts with a Chinese city/prefix."""
    skip: set[str] = set()
    for c in companies:
        slug = c.get("slug")
        name = c.get("name") or ""
        if slug and _TRANSLITERATED_CHINESE_RE.match(name):
            skip.add(str(slug))
    return skip


async def classify_low_value_buyers(
    companies: List[Dict[str, Any]],
    timeout: float = 20.0,
) -> Dict[str, set[str]]:
    """Return exclusion sets for the two-pager classifier.

    Uses ONLY the hardcoded regex blocklist (Amazon/Walmart subsidiaries,
    "freight"/"logistics" keywords, Asian brand US arms). The Haiku
    long-tail classifier was dropped because it over-filtered legitimate
    mid-market prospects.

    `timeout` is retained for signature compatibility with earlier callers.

    Returns {"hard": set[str], "soft": set[str]} where `soft` is always
    empty. Caller treats `hard` as never-readmit and `soft` as topup pool;
    with no soft suggestions the table simply runs short when the hard
    blocklist filters a lot of rows out.
    """
    targets = [c for c in companies if c.get("slug") and c.get("name")]
    if not targets:
        return {"hard": set(), "soft": set()}

    hard = _hard_blocklist_slugs(targets)
    hard |= _notify_party_forwarder_slugs(targets)
    hard |= _transliterated_chinese_slugs(targets)

    if hard:
        logger.info(
            f"[TwoPager/classify] hard blocklist skipped {len(hard)}/{len(targets)}: "
            f"{[c.get('name') for c in targets if c.get('slug') in hard]}"
        )
    else:
        logger.info(f"[TwoPager/classify] hard blocklist skipped 0/{len(targets)}")
    return {"hard": hard, "soft": set()}
