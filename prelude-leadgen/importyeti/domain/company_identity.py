"""Company-name normalization and two-pager company dedup helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


# ── Dedup alias map: maps normalized name variants → canonical key ──────────
DEDUPE_ALIAS_MAP: Dict[str, str] = {
    "icon health and fitness": "icon health and fitness",
    "ifit": "icon health and fitness",
    "icon h and f": "icon health and fitness",
    "kerry apex sfo": "kerry apex",
    "kerry apex nyc": "kerry apex",
    "kerry apex lax": "kerry apex",
    "dell products lp": "dell products",
    "dell products l p aw1": "dell products",
    "dell product lp": "dell products",
    "pacific home and garden": "pacific home garden",
    "pacific home garden": "pacific home garden",
}

# Legal suffix pattern stripped during normalization.
LEGAL_SUFFIX_RE = re.compile(
    r"\b(llc|inc|corp|corporation|co|company|ltd|lp|l p)\b\.?$"
)


def normalize_company_name(name: str) -> str:
    """Lowercase, ASCII-fold, replace & with and, strip punctuation,
    collapse whitespace, strip legal suffixes."""
    s = name.lower().strip()
    # ASCII-fold (e.g. é → e)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", "and")
    # Strip punctuation (keep spaces and alphanumeric)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Strip legal suffixes (repeat in case of e.g. "co inc")
    for _ in range(3):
        prev = s
        s = LEGAL_SUFFIX_RE.sub("", s).strip()
        if s == prev:
            break
    return s.strip()


def dedupe_companies(companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge duplicate companies by normalized name root.

    Merge key: normalized_name_root. When root has ≤3 tokens, city is
    included in the key to guard against over-merging short names.

    Cluster merge: sum weight_kg + matching_shipments. Keep highest-
    volume member's slug/name/city/state as canonical. Union
    supplier_breakdown (de-dup by supplier_name). Carry forward any
    validated_* contact fields from any member.
    """
    clusters: Dict[str, List[Dict[str, Any]]] = {}

    for comp in companies:
        raw_name = comp.get("name") or ""
        norm = normalize_company_name(raw_name)
        # Apply alias map
        norm = DEDUPE_ALIAS_MAP.get(norm, norm)
        tokens = norm.split()
        if len(tokens) <= 3:
            city = (comp.get("city") or "").lower().strip()
            key = f"{norm}|{city}"
        else:
            key = norm
        clusters.setdefault(key, []).append(comp)

    merged: List[Dict[str, Any]] = []
    for members in clusters.values():
        if len(members) == 1:
            merged.append(members[0])
            continue
        # Canonical = highest weight_kg member
        canonical = max(members, key=lambda c: float(c.get("weight_kg") or 0))
        result = dict(canonical)
        # Sum weight_kg and matching_shipments
        result["weight_kg"] = sum(float(c.get("weight_kg") or 0) for c in members)
        result["matching_shipments"] = sum(
            int(c.get("matching_shipments") or 0) for c in members
        )
        # Union supplier_breakdown by supplier_name
        sb_map: Dict[str, Dict[str, Any]] = {}
        for c in members:
            sb = c.get("supplier_breakdown")
            if not isinstance(sb, list):
                continue
            for entry in sb:
                if not isinstance(entry, dict):
                    continue
                sname = entry.get("supplier_name") or ""
                if sname not in sb_map:
                    sb_map[sname] = entry
        if sb_map:
            result["supplier_breakdown"] = list(sb_map.values())
        # Carry forward validated_* fields from any member
        for c in members:
            for field in ("validated_email", "validated_contact_name", "validated_contact_title"):
                if c.get(field) and not result.get(field):
                    result[field] = c[field]
        merged.append(result)

    return merged
