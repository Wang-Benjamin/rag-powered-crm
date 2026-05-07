"""Email domain validation for lead enrichment.

Deterministic checks — no LLM or API calls. Catches:
  1. Generic email providers (gmail, yahoo, etc.)
  2. Foreign TLDs on US/CA leads (.co.in, .mx, .es, etc.)
  3. Suspicious domain keywords (dubai, treatment, etc.)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Generic providers — a trade company won't use these for business contacts
_GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "yandex.com", "163.com",
    "qq.com", "126.com", "live.com", "msn.com",
})

# Country-code TLDs that indicate a foreign entity when the lead is in the US/Canada
_FOREIGN_TLDS = frozenset({
    ".co.in", ".in", ".mx", ".es", ".de", ".fr", ".it", ".cn", ".jp",
    ".kr", ".br", ".ru", ".ae", ".pk", ".ng", ".za", ".ke", ".sg",
    ".tw", ".hk", ".ph", ".vn", ".th", ".id", ".my", ".bd",
})

# Domain keywords that suggest a wrong-entity match
_SUSPICIOUS_DOMAIN_KEYWORDS = frozenset({
    "dubai", "treatment", "hospital", "clinic", "therapy", "medical",
    "church", "school", "university", "nonprofit",
})


def validate_email_domain(
    email: str,
    lead_state: Optional[str] = None,
    lead_country: str = "US",
) -> tuple[bool, str]:
    """Check if an email domain is plausible for the lead's geography.

    Returns (is_valid, reason).  Deterministic — no LLM or API call.
    """
    if not email or "@" not in email:
        return False, "no_email"

    domain = email.rsplit("@", 1)[1].lower()

    # 1. Block generic providers
    if domain in _GENERIC_EMAIL_DOMAINS:
        return False, f"generic_provider:{domain}"

    # 2. Block foreign TLDs when lead is US/CA
    if lead_country in ("US", "CA"):
        for tld in _FOREIGN_TLDS:
            if domain.endswith(tld):
                return False, f"foreign_tld:{tld}"

    # 3. Block suspicious domain keywords
    for kw in _SUSPICIOUS_DOMAIN_KEYWORDS:
        if kw in domain:
            return False, f"suspicious_keyword:{kw}"

    return True, "ok"
