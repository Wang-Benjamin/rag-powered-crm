"""Buyer source loaders for two-pager reports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from importyeti.clients import internal_bol_client
from importyeti.contracts.buyer_cache_contract import write_buyer_cache_batch
from importyeti.domain.transformers import compute_supplier_company_yoy

# HS-code-specific shipment range overrides for the PowerQuery filter.
# Key: first 4 digits of HS code. Value: (floor, ceiling) for
# company_total_shipments. Default: (12, 2000). Floor was 1000 (targeting
# established brands Apollo reliably indexes) but that left thin HS codes
# (e.g. 9401.30 office chairs) returning ≤2 importers from IY. Loosening to
# 12 catches small-but-real US importers; ceiling 2000 still excludes
# Fortune-500 mega-retailers and freight consolidators. Apollo enrichment
# may miss more often, but the synth-contact fallback covers those cards.
# No per-category overrides right now — kept as empty dict for future use.
HS_FILTER_OVERRIDES: dict[str, tuple[int, int]] = {}


async def fetch_buyers_cached(*, client, hs_code: Optional[str] = None, product_description: Optional[str] = None, auth_token: str, logger) -> Dict[str, Any]:
    if not hs_code and not product_description:
        raise ValueError("fetch_buyers_cached requires at least one of hs_code or product_description")
    # max_results=80 gives blocklist + dedupe + real-filter enough headroom
    # to land the post-filter pool ≥30 (which the two-pager top_15 = top_3 +
    # backfill_12 selection then narrows from). 45 was too tight in CN-heavy
    # categories where transliterated-name + freight-keyword regex drops alone
    # can shed 20+ rows.
    cached = await internal_bol_client.search_cache(
        hs_codes=[hs_code] if hs_code else None,
        products=[product_description] if product_description else None,
        max_results=80, auth_token=auth_token, slim=True,
    )
    if not cached:
        return {"total_companies": None, "companies": [], "total_weight_kg": 0, "from_cache": False}

    companies = []
    total_weight_kg = 0.0
    for comp in cached:
        slug = (
            comp.get("importyeti_slug") or comp.get("importyetiSlug")
            or comp.get("slug") or comp.get("company_slug") or ""
        )
        if not slug:
            continue
        weight = comp.get("weight_kg") or comp.get("weightKg") or 0
        total_weight_kg += weight

        city = comp.get("city")
        state = comp.get("state")
        address = comp.get("address") or comp.get("company_address")
        if not city and address:
            if isinstance(address, str):
                _, city, state = client.parse_address([{"key": address}])
            elif isinstance(address, list):
                _, city, state = client.parse_address(address)

        trend_yoy = None
        ts = comp.get("time_series") or comp.get("timeSeries")
        if ts and isinstance(ts, dict):
            yoy = compute_supplier_company_yoy(ts)
            if yoy is not None:
                trend_yoy = round(yoy * 100, 1)
        yoy_raw = comp.get("supplier_company_yoy") or comp.get("supplierCompanyYoy")
        if trend_yoy is None and yoy_raw is not None:
            trend_yoy = round(float(yoy_raw) * 100, 1)

        supplier_count = None
        sb = comp.get("supplier_breakdown") or comp.get("supplierBreakdown")
        if sb and isinstance(sb, list):
            supplier_count = len(sb)

        name = comp.get("company_name") or comp.get("companyName") or comp.get("name") or ""
        matching = comp.get("matching_shipments") or comp.get("matchingShipments")
        recent = comp.get("most_recent_shipment") or comp.get("mostRecentShipment")

        # Manual seed path: scripts/seed_two_pager_contacts.py writes known
        # Apollo results into bol_companies.validated_email /
        # validated_contact_name so the two-pager short-circuits the Apollo
        # call. Pass those through here; the contact_adapter checks them
        # before hitting Apollo.
        validated_email = comp.get("validated_email") or comp.get("validatedEmail")
        validated_contact_name = (
            comp.get("validated_contact_name") or comp.get("validatedContactName")
        )
        validated_contact_title = (
            comp.get("validated_contact_title") or comp.get("validatedContactTitle")
        )

        companies.append({
            "slug": slug,
            "name": name,
            "city": city,
            "state": state,
            "matching_shipments": matching,
            "weight_kg": weight,
            "most_recent_shipment": recent,
            "supplier_count": supplier_count,
            "trend_yoy": trend_yoy,
            # supplier_breakdown / time_series are NOT included here under
            # slim=True (the 8007 cache strips heavy JSONB on slim search).
            # They get filled in by the per-slug hydrate step in
            # two_pager_service after pool[:30] selection.
            "validated_email": validated_email,
            "validated_contact_name": validated_contact_name,
            "validated_contact_title": validated_contact_title,
        })

    companies.sort(key=lambda c: c.get("matching_shipments") or 0, reverse=True)
    logger.info(f"[TwoPager] Cache hit: {len(companies)} buyers for {hs_code or product_description!r}")
    return {
        "total_companies": len(companies),
        "companies": companies,
        "total_weight_kg": total_weight_kg,
        "from_cache": True,
    }


async def fetch_buyers_api(*, client, hs_code: Optional[str] = None, product_description: Optional[str] = None, auth_token: str, logger) -> Dict[str, Any]:
    if not hs_code and not product_description:
        raise ValueError("fetch_buyers_api requires at least one of hs_code or product_description")
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=182)).strftime("%m/%d/%Y")
    end_date = now.strftime("%m/%d/%Y")

    hs_prefix = hs_code[:4] if hs_code else None
    lo, hi = HS_FILTER_OVERRIDES.get(hs_prefix, (12, 2000)) if hs_prefix else (12, 2000)
    shipments_range = f"{lo} TO {hi}"

    # Fetch 45 to give the real-company filter headroom — after dropping shells
    # + dedup, we need at least 15 legit buyers in the pool.
    response = await client.power_query_buyers(
        hs_code=f"{hs_code}*" if hs_code else None,
        product_description=product_description,
        page_size=45,
        supplier_country="china",
        company_total_shipments=shipments_range,
        start_date=start_date,
        end_date=end_date,
    )
    total_companies = response.data.totalCompanies if response.data else None
    raw_companies = response.data.data if response.data else []
    raw_companies.sort(key=lambda c: c.doc_count or 0, reverse=True)

    companies = []
    total_weight_kg = 0.0
    cache_companies = []
    cache_search_results = []
    for comp in raw_companies:
        slug = client.extract_slug(comp.company_link or "")
        if not slug:
            continue
        address_list = [kc.model_dump() for kc in comp.company_address] if comp.company_address else None
        _, city, state = client.parse_address(address_list)
        weight = comp.weight or 0
        total_weight_kg += weight
        companies.append({
            "slug": slug,
            "name": comp.key,
            "city": city,
            "state": state,
            "matching_shipments": comp.doc_count,
            "weight_kg": weight,
        })
        address_str = address_list[0]["key"] if address_list else None
        cache_companies.append({
            "importyeti_slug": slug,
            "company_name": comp.key,
            "address": address_str,
            "city": city,
            "state": state,
            "country": "USA",
            "weight_kg": weight,
            "matching_shipments": comp.doc_count,
            "teu": comp.teu,
            "enrichment_status": "pending",
        })
        # HS-keyed cache writeback works for both modes: we derive the HS from the
        # PowerQuery response's per-company HS aggregation, not from the caller's
        # query. In product mode this enriches the HS-indexed cache even though the
        # caller searched by product description.
        # Cross-pollination is expected: a product-mode search from tenant A writes
        # HS-keyed rows that tenant B's HS search then reads (8007 cache is shared).
        hs_list = comp.hs_code  # Optional[List[KeyCount]]; KeyCount has .key and .doc_count
        if hs_list:
            top_hs = max(hs_list, key=lambda kc: kc.doc_count).key
            cache_search_results.append({
                "importyeti_slug": slug,
                "hs_code": top_hs,
                "matching_shipments": comp.doc_count,
                "weight_kg": weight,
                "teu": comp.teu,
            })
        else:
            logger.warning(f"[TwoPager] Skipping cache writeback for slug={slug}: no HS codes on PowerQuery response")

    if cache_companies and auth_token:
        try:
            await write_buyer_cache_batch(
                companies=cache_companies,
                search_results=cache_search_results,
                auth_token=auth_token,
            )
        except Exception as e:
            logger.warning(f"[TwoPager] Buyer cache write failed: {e}")

    return {
        "total_companies": total_companies,
        "companies": companies,
        "total_weight_kg": total_weight_kg,
        "from_cache": False,
    }


