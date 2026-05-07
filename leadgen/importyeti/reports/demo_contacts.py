"""Demo contact synthesis for two-pager reports when real contacts are scarce.

Synthesizes plausible contact names and titles plus template-preview emails
with visible [CONTACT NAME] / [COMPANY NAME] placeholders. Emails are sent
to demo+<slug>@preludeos.com addresses so they can never be confused with
real outreach. Always marks entries with is_synthesized=true.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEMO_EMAIL_RE = re.compile(r"^demo\+[a-z0-9-]+@preludeos\.com$")

_DEMO_TITLES = [
    "Head of Sourcing",
    "Director of Procurement",
    "VP Supply Chain",
    "Operations Manager",
    "Senior Buyer",
]
# Neutral placeholder names — deliberately generic so users don't confuse with real people.
_DEMO_FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan"]
_DEMO_LAST_NAMES = ["Chen", "Patel", "Garcia", "Smith", "Kim"]


def _slugify(text: str) -> str:
    """Lowercase + replace non-alphanumerics with hyphens for demo+ email addresses."""
    clean = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return clean or "buyer"


def synthesize_demo_contact(
    *,
    buyer_slug: str,
    buyer_name: str,
    subject: str,
    index: int = 0,
) -> Dict[str, Any]:
    """Generate a single deterministic demo contact. Uses index as a rotating
    offset into the title/name pools so sibling slots in the same report look
    varied rather than identical.
    """
    slug_key = _slugify(buyer_slug)
    first = _DEMO_FIRST_NAMES[index % len(_DEMO_FIRST_NAMES)]
    last = _DEMO_LAST_NAMES[index % len(_DEMO_LAST_NAMES)]
    title = _DEMO_TITLES[index % len(_DEMO_TITLES)]
    email = f"demo+{slug_key}@preludeos.com"
    assert DEMO_EMAIL_RE.match(email), f"Demo email format broken: {email}"

    subject_line = f"{subject or 'Sourcing'} partnership — intro from Prelude (demo)"
    body = (
        f"Hi [CONTACT NAME],\n\n"
        f"I'm reaching out from Prelude — we help overseas suppliers connect with "
        f"US buyers like [COMPANY NAME] who import {subject or 'these goods'} "
        f"from China. Based on your recent trade activity, I thought there might "
        f"be a fit.\n\n"
        f"Would you be open to a 15-minute intro call next week?\n\n"
        f"Best,\n[YOUR NAME]\n\n"
        f"— This is a demo contact generated for preview purposes. [CONTACT NAME] "
        f"and [COMPANY NAME] are placeholders."
    )

    return {
        "slug": buyer_slug,
        "name": f"{first} {last}",
        "title": title,
        "email": email,
        "email_subject": subject_line,
        "email_body": body,
        "is_synthesized": True,
    }


