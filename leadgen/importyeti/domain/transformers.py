"""
Standalone transformation functions for ImportYeti data → scoring dicts.
Used by bol_search_service.py and tests.
"""

import re
import statistics
from datetime import date as date_type, datetime, timedelta
from typing import List, Dict, Any, Optional

JUNK_NAMES = {"Missing in source document", "", "N/A", "None"}


def normalize_supplier_breakdown(raw_suppliers_table: list) -> list:
    """
    Transform raw /company/{company} suppliers_table entries into
    the normalized supplier_breakdown format expected by scoring.py.

    Raw keys from API: supplier_name, country, total_shipments_company,
    shipments_percents_company, shipments_12m, shipments_12_24m,
    total_weight, total_teus, most_recent_shipment, is_new_supplier,
    supplier_address_country (fallback for country)
    """
    result = []
    for s in raw_suppliers_table:
        if s.get("supplier_name") in JUNK_NAMES:
            continue
        result.append({
            "supplier_name": s.get("supplier_name", ""),
            "country": s.get("country") or s.get("supplier_address_country") or "",
            "shipments": s.get("total_shipments_company", 0),
            "shipments_percents_company": s.get("shipments_percents_company", 0),
            "shipments_12m": s.get("shipments_12m", 0),
            "shipments_12_24m": s.get("shipments_12_24m", 0),
            "weight_kg": s.get("total_weight", 0),
            "teu": s.get("total_teus", 0),
            "most_recent_shipment": s.get("most_recent_shipment", ""),
            "is_new_supplier": s.get("is_new_supplier", False),
        })
    return result


def build_company_data(
    most_recent_shipment: Optional[str] = None,
    total_suppliers: Optional[int] = None,
    company_total_shipments: Optional[int] = None,
    supplier_breakdown: Optional[list] = None,
    avg_order_cycle_days: Optional[int] = None,
    # From hs_metrics JSONB (available pre-enrichment):
    matching_shipments: Optional[int] = None,
    weight_kg: Optional[float] = None,
    teu: Optional[float] = None,
    # Computed from time_series (deep enrichment only):
    derived_growth_12m_pct: Optional[float] = None,
    derived_supplier_hhi: Optional[float] = None,
    derived_order_regularity_cv: Optional[float] = None,
) -> dict:
    """Build company_data dict for scoring.py from available fields."""
    return {
        "most_recent_shipment": most_recent_shipment,
        "total_suppliers": total_suppliers,
        "company_total_shipments": company_total_shipments,
        "supplier_breakdown": supplier_breakdown,
        "avg_order_cycle_days": avg_order_cycle_days,
        "matching_shipments": matching_shipments,
        "weight_kg": weight_kg,
        "teu": teu,
        "derived_growth_12m_pct": derived_growth_12m_pct,
        "derived_supplier_hhi": derived_supplier_hhi,
        "derived_order_regularity_cv": derived_order_regularity_cv,
    }


def build_query_data(
    china_concentration: Optional[float] = None,
    cn_dominated_hs_code: bool = False,
    supplier_company_yoy: Optional[float] = None,
) -> dict:
    """Build query_data dict for scoring.py from available fields."""
    return {
        "china_concentration": china_concentration,
        "cn_dominated_hs_code": cn_dominated_hs_code,
        "supplier_company_yoy": supplier_company_yoy,
    }


def compute_china_concentration(time_series: dict) -> Optional[float]:
    """
    Compute china_concentration % from deep enrichment time_series.
    time_series is a dict of {date_str: {shipments, china_shipments, ...}}.
    Returns percentage (0-100) or None if no data.
    """
    total = 0
    china = 0
    for month_data in time_series.values():
        total += month_data.get("shipments", 0)
        china += month_data.get("china_shipments", 0)
    if total == 0:
        return None
    return (china / total) * 100



def compute_avg_order_cycle_days(time_series: dict) -> Optional[int]:
    """
    Compute average order cycle in days from deep enrichment time_series.

    Uses the last 24 months only (recent behavior, not historical).
    Looks at gaps between months WITH shipments to estimate how often
    the company places orders.

    Returns None if insufficient data or if the company ships every month
    (cycle < 35 days is unreliable from monthly data).
    """
    if not time_series:
        return None

    today = date_type.today()
    cutoff = today - timedelta(days=730)  # last 24 months

    # Parse all months within the last 24 months
    monthly = []
    for date_str, data in time_series.items():
        for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                if dt >= cutoff:
                    monthly.append((dt, data.get("shipments", 0)))
                break
            except ValueError:
                continue

    if len(monthly) < 6:
        return None

    monthly.sort(key=lambda x: x[0])

    total_months = len(monthly)
    active_months = sum(1 for _, s in monthly if s > 0)

    if active_months == 0:
        return None

    # If they ship nearly every month, cycle is ~30 days — too granular
    # for monthly data to be meaningful. Return None to use fallback.
    active_ratio = active_months / total_months
    if active_ratio > 0.8:
        return None

    # Estimate cycle: total span / number of active months
    span_days = (monthly[-1][0] - monthly[0][0]).days
    if span_days == 0 or active_months < 2:
        return None

    cycle = span_days // (active_months - 1)
    return max(35, cycle)  # floor at 35 days (monthly data can't go lower)


def compute_supplier_company_yoy(time_series: dict) -> Optional[float]:
    """
    Compute year-over-year shipment change from time_series.
    Compares last 12 months vs prior 12 months.
    Returns fractional change (e.g., -0.15 = 15% decline) or None.
    """
    if not time_series:
        return None

    today = date_type.today()
    cutoff_12m = today - timedelta(days=365)
    cutoff_24m = today - timedelta(days=730)

    last_12m = 0
    prior_12m = 0

    for date_str, data in time_series.items():
        for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                shipments = data.get("shipments", 0)
                if dt >= cutoff_12m:
                    last_12m += shipments
                elif dt >= cutoff_24m:
                    prior_12m += shipments
                break
            except ValueError:
                continue

    if prior_12m == 0:
        return None

    return (last_12m - prior_12m) / prior_12m


# ─── Derived metric helpers (S9, S10, S11 scoring signals) ────────


def _parse_time_series_months(time_series: dict) -> list[tuple[date_type, dict]]:
    """Parse time_series keys into (date, data) pairs sorted by date."""
    result = []
    for date_str, data in time_series.items():
        for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                result.append((dt, data))
                break
            except ValueError:
                continue
    result.sort(key=lambda x: x[0])
    return result


def compute_growth_12m(time_series: dict) -> Optional[float]:
    """YoY shipment growth %. Compares last 12m vs prior 12m of time_series.
    Returns percentage (e.g., 25.0 for 25% growth) or None."""
    if not time_series:
        return None

    today = date_type.today()
    cutoff_12m = today - timedelta(days=365)
    cutoff_24m = today - timedelta(days=730)

    last_12m, prior_12m = 0, 0
    for dt, data in _parse_time_series_months(time_series):
        shipments = data.get("shipments", 0)
        if dt >= cutoff_12m:
            last_12m += shipments
        elif dt >= cutoff_24m:
            prior_12m += shipments

    if prior_12m == 0:
        return None
    return ((last_12m - prior_12m) / prior_12m) * 100


def compute_supplier_hhi(supplier_breakdown: list) -> Optional[float]:
    """Herfindahl-Hirschman Index from supplier shipment shares.
    Sum of squared share fractions for active suppliers. Range 0-1.
    Returns None if no active suppliers."""
    if not supplier_breakdown:
        return None

    active = [s for s in supplier_breakdown if (s.get("shipments_12m") or 0) > 0]
    if not active:
        return None

    total = sum(s.get("shipments_12m") or 0 for s in active)
    if total == 0:
        return None

    return sum(((s.get("shipments_12m") or 0) / total) ** 2 for s in active)


def compute_order_regularity_cv(time_series: dict) -> Optional[float]:
    """Coefficient of variation of monthly shipments over last 36 months.
    CV = stddev / mean. Higher = more erratic ordering.
    Returns None if insufficient data (<6 active months)."""
    if not time_series:
        return None

    today = date_type.today()
    cutoff = today - timedelta(days=1095)  # 36 months

    monthly_shipments = []
    for dt, data in _parse_time_series_months(time_series):
        if dt >= cutoff:
            monthly_shipments.append(data.get("shipments", 0))

    # Need at least 6 active (non-zero) months for a meaningful CV
    active = [s for s in monthly_shipments if s > 0]
    if len(active) < 6:
        return None

    mean = statistics.mean(monthly_shipments)
    if mean == 0:
        return None

    return statistics.stdev(monthly_shipments) / mean


def derive_most_recent_shipment(time_series: dict) -> Optional[str]:
    """Derive most_recent_shipment from deep-enrich time_series.

    Finds the latest month with shipments > 0 and returns its first day
    in dd/mm/yyyy format (matching ImportYeti's date convention).
    """
    if not time_series:
        return None

    active_months = [
        (dt, data)
        for dt, data in _parse_time_series_months(time_series)
        if data.get("shipments", 0) > 0
    ]
    if not active_months:
        return None

    latest_date = max(active_months, key=lambda x: x[0])[0]
    return latest_date.strftime("%d/%m/%Y")


def compute_china_concentration_12m(time_series: dict) -> Optional[float]:
    """China concentration % from last 12 months of time_series.
    More current than all-time concentration from supplier_breakdown.
    Returns percentage (0-100) or None."""
    if not time_series:
        return None

    today = date_type.today()
    cutoff = today - timedelta(days=365)

    total, china = 0, 0
    for dt, data in _parse_time_series_months(time_series):
        if dt >= cutoff:
            total += data.get("shipments", 0)
            china += data.get("china_shipments", 0)

    if total == 0:
        return None
    return (china / total) * 100


# ─── Address / dedup helpers (extracted from importyeti_router) ────────────────

_US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN',
    'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
    'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
    'TX','UT','VT','VA','WA','WV','WI','WY','DC',
}
_US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
_CA_PROVINCES = {'AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'}
_STREET_SUFFIXES = {
    'ave','avenue','st','street','dr','drive','blvd','boulevard','rd','road',
    'ct','court','ln','lane','pkwy','parkway','hwy','highway','pl','place',
    'way','fl','floor','ste','suite','unit','circle','cir','terrace','ter',
    'ctr','center','centre','park',
}
_ADDRESS_NOISE_RE = re.compile(
    r'\s+(?:Tel|Fax|Phone|Ph|Email|Te|Teemail|T|F)\b[\s:=]*.*$',
    re.IGNORECASE,
)
_COUNTRY_TRAILER_RE = re.compile(r'\b(United States|USA|US|Canada)\b.*$', re.IGNORECASE)
_SPACE_RE = re.compile(r'\s+')
_US_STATE_ZIP_RE = re.compile(
    r'\b(?:[A-Za-z]{2}\s+)?(?P<state>[A-Za-z]{2})\s*-?\s*\d{5}(?:-?\d{4})?\b',
    re.IGNORECASE,
)
_US_STATE_NAME_ZIP_RE = re.compile(
    r'\b(?P<state_name>'
    + '|'.join(re.escape(name) for name in sorted(_US_STATE_NAMES, key=len, reverse=True))
    + r')\s+\d{5}(?:-?\d{4})?\b',
    re.IGNORECASE,
)
_CA_PROVINCE_POSTAL_RE = re.compile(
    r'\b(?P<province>[A-Za-z]{2})\s+[A-Z]\d[A-Z]\s*\d[A-Z]\d\b',
    re.IGNORECASE,
)


def normalize_for_dedup(s: str) -> str:
    """Normalize a string for dedup comparison (case-insensitive, trimmed)."""
    return (s or "").strip().lower()


def _normalize_address_candidate(candidate: str) -> str | None:
    if not candidate:
        return None
    cleaned = _SPACE_RE.sub(" ", candidate.replace("\n", " ")).strip(" ,;")
    cleaned = _ADDRESS_NOISE_RE.sub("", cleaned).strip(" ,;")
    cleaned = _COUNTRY_TRAILER_RE.sub(lambda m: m.group(1), cleaned).strip(" ,;")
    return cleaned or None


def _address_candidates(address: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for part in (address or "").split("@@")[0].split(","):
        candidate = _normalize_address_candidate(part)
        if candidate and candidate.lower() not in seen:
            candidates.append(candidate)
            seen.add(candidate.lower())

    fallback = _normalize_address_candidate(address or "")
    if fallback and fallback.lower() not in seen:
        candidates.append(fallback)
    return candidates


def _format_city(city: str) -> str:
    return " ".join(
        part.capitalize() if part.isupper() or part.islower() else part
        for part in city.split()
    )


def _city_from_prefix(prefix: str) -> str | None:
    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*|\d+", prefix)
    city_words: list[str] = []
    for token in reversed(tokens):
        lower = token.lower().strip(".")
        if token.isdigit() or lower in _STREET_SUFFIXES:
            break
        city_words.insert(0, token)
        if len(city_words) >= 3:
            break
    if not city_words:
        return None
    return _format_city(" ".join(city_words))


def _extract_city_state(candidate: str) -> str | None:
    normalized = _normalize_address_candidate(candidate)
    if not normalized:
        return None

    for match in _US_STATE_ZIP_RE.finditer(normalized):
        state = match.group("state").upper()
        if state not in _US_STATES:
            continue
        city = _city_from_prefix(normalized[:match.start()].strip(" ,;"))
        if city:
            return f"{city}, {state}"

    for match in _US_STATE_NAME_ZIP_RE.finditer(normalized):
        state = _US_STATE_NAMES[match.group("state_name").lower()]
        city = _city_from_prefix(normalized[:match.start()].strip(" ,;"))
        if city:
            return f"{city}, {state}"

    for match in _CA_PROVINCE_POSTAL_RE.finditer(normalized):
        province = match.group("province").upper()
        if province not in _CA_PROVINCES:
            continue
        city = _city_from_prefix(normalized[:match.start()].strip(" ,;"))
        if city:
            return f"{city}, {province}"

    return None


def parse_city_state(address: str) -> str:
    """Extract a display locality from raw ImportYeti address text.

    Returns ``City, ST``/``City, Province`` when parseable.  Unparseable raw
    address blobs are intentionally collapsed to ``Unknown`` so lead de-dupe
    never receives comma-joined multi-address strings as a location.
    """
    for candidate in _address_candidates(address):
        parsed = _extract_city_state(candidate)
        if parsed:
            return parsed
    return "Unknown"


# Fields to strip from blurred companies (trial users, rank 51+)
_BLURRED_FIELDS = [
    "website",
    "supplierBreakdown", "supplier_breakdown",
    "aiActionBrief", "ai_action_brief",
    "phoneNumber", "phone_number",
]

_COMPETITOR_BLURRED_FIELDS = [
    "overlap_count", "overlapCount",
    "overlap_buyer_slugs", "overlapBuyerSlugs",
    "companies_table", "companiesTable",
    "customer_concentration", "customerConcentration",
    "trend_yoy", "trendYoy",
    "threat_score", "threatScore",
    "buyer_teu", "buyerTeu",
    "buyer_share_pct", "buyerSharePct",
]


def apply_trial_blur(companies: List[Dict[str, Any]], visible_limit: int) -> List[Dict[str, Any]]:
    """
    For trial users, strip detail from companies ranked beyond visible_limit.
    Companies are assumed to be pre-sorted by score (descending).
    Returns the mutated list with is_blurred flags.
    visible_limit < 0 means unlimited — no rows are blurred.
    """
    unlimited = visible_limit < 0
    for idx, company in enumerate(companies):
        if unlimited or idx < visible_limit:
            company["is_blurred"] = False
        else:
            for field in _BLURRED_FIELDS:
                company[field] = None
            company["is_blurred"] = True
    return companies


def apply_competitor_blur(competitors: list, visible_limit: int) -> list:
    """Mark competitors beyond visible_limit as blurred, stripping sensitive fields.
    visible_limit < 0 means unlimited — no rows are blurred.
    """
    unlimited = visible_limit < 0
    for idx, comp in enumerate(competitors):
        if unlimited or idx < visible_limit:
            comp["is_blurred"] = False
        else:
            for field in _COMPETITOR_BLURRED_FIELDS:
                comp[field] = None
            comp["is_blurred"] = True
    return competitors


def redact_buyer_personnel_emails(companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Strip `email` from every personnel record. Enforces the show_buyer_emails
    entitlement server-side so emails never ship in API responses for tenants
    that don't have buyer-email access.
    """
    for company in companies:
        personnel = company.get("personnel")
        if not personnel:
            continue
        for person in personnel:
            if isinstance(person, dict):
                person.pop("email", None)
    return companies
