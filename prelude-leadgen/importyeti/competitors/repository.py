"""Persistence helpers for competitor rows and subscription-backed HS metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from importyeti.contracts.subscription import get_tenant_hs_codes

from .common import (
    extract_city_from_address,
    json_or_none,
    list_or_empty,
    list_or_none,
    merge_hs_codes,
    normalize_trend_yoy,
)


async def get_hs_descriptions(conn, logger) -> Dict[str, str]:
    try:
        hs_data = await get_tenant_hs_codes(conn)
        if not hs_data:
            return {}

        return {
            item.get("code").replace(".", ""): item.get("description", item.get("code"))
            for item in hs_data
            if item.get("code") and item.get("confirmed")
        }
    except Exception as e:
        logger.warning(f"[Competitors] Failed to get HS descriptions: {e}")
        return {}


async def current_hs_codes(conn, logger) -> set[str]:
    hs_descriptions = await get_hs_descriptions(conn, logger)
    return set(hs_descriptions.keys())


async def upsert_competitor(
    *,
    conn,
    supplier_slug: str,
    supplier_name: str,
    address: Optional[str],
    country_code: str,
    hs_codes: List[str],
    total_shipments: Optional[int],
    matching_shipments: Optional[int],
    total_customers: Optional[int],
    customer_companies: List[str],
    specialization: Optional[float],
    weight_kg: Optional[float],
    product_descriptions: List[str],
    logger,
) -> None:
    city = extract_city_from_address(address)
    try:
        await conn.execute(
            """
            INSERT INTO bol_competitors (
                supplier_slug, supplier_name, country, country_code, address, city,
                hs_codes, total_shipments, total_customers, matching_shipments,
                specialization, weight_kg, customer_companies, product_descriptions,
                first_seen_at, last_updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $14,
                $6, $7, $8, $9,
                $10, $11, $12, $13,
                NOW(), NOW()
            )
            ON CONFLICT (supplier_slug) DO UPDATE SET
                supplier_name = EXCLUDED.supplier_name,
                address = COALESCE(EXCLUDED.address, bol_competitors.address),
                city = COALESCE(EXCLUDED.city, bol_competitors.city),
                hs_codes = (
                    SELECT ARRAY(SELECT DISTINCT unnest(bol_competitors.hs_codes || EXCLUDED.hs_codes))
                ),
                total_shipments = COALESCE(EXCLUDED.total_shipments, bol_competitors.total_shipments),
                total_customers = COALESCE(EXCLUDED.total_customers, bol_competitors.total_customers),
                matching_shipments = GREATEST(EXCLUDED.matching_shipments, bol_competitors.matching_shipments),
                specialization = COALESCE(EXCLUDED.specialization, bol_competitors.specialization),
                weight_kg = COALESCE(EXCLUDED.weight_kg, bol_competitors.weight_kg),
                customer_companies = (
                    SELECT ARRAY(SELECT DISTINCT unnest(bol_competitors.customer_companies || EXCLUDED.customer_companies))
                ),
                product_descriptions = (
                    SELECT ARRAY(SELECT DISTINCT unnest(bol_competitors.product_descriptions || EXCLUDED.product_descriptions))
                ),
                last_updated_at = NOW()
            """,
            supplier_slug,
            supplier_name,
            "China" if country_code == "CN" else None,
            country_code,
            address,
            hs_codes,
            total_shipments,
            total_customers,
            matching_shipments,
            specialization,
            weight_kg,
            customer_companies,
            product_descriptions,
            city,
        )
    except Exception as e:
        logger.warning(f"[Competitors] Upsert failed for {supplier_slug}: {e}")


async def upsert_cached_competitor(
    *,
    conn,
    hs_code: str,
    competitor: Dict[str, Any],
    supplier_slug: str,
    logger,
) -> None:
    country_code = competitor.get("country_code") or "CN"
    address = competitor.get("address")

    await upsert_competitor(
        conn=conn,
        supplier_slug=supplier_slug,
        supplier_name=competitor.get("supplier_name") or competitor.get("name") or "",
        address=address,
        country_code=country_code,
        hs_codes=merge_hs_codes(competitor.get("hs_codes"), hs_code),
        total_shipments=competitor.get("total_shipments"),
        matching_shipments=competitor.get("matching_shipments"),
        total_customers=competitor.get("total_customers"),
        customer_companies=list_or_empty(competitor.get("customer_companies")),
        specialization=competitor.get("specialization"),
        weight_kg=competitor.get("weight_kg"),
        product_descriptions=list_or_empty(competitor.get("product_descriptions")),
        logger=logger,
    )

    trend_yoy = normalize_trend_yoy(competitor.get("trend_yoy"))
    time_series = json_or_none(competitor.get("time_series"))
    companies_table = json_or_none(competitor.get("companies_table"))
    recent_bols = json_or_none(competitor.get("recent_bols"))
    carriers_per_country = json_or_none(competitor.get("carriers_per_country"))

    try:
        await conn.execute(
            """
            UPDATE bol_competitors
            SET supplier_name_cn = COALESCE($1, supplier_name_cn),
                city = COALESCE($2, city),
                time_series = COALESCE($3::jsonb, time_series),
                trend_yoy = COALESCE($4, trend_yoy),
                companies_table = COALESCE($5::jsonb, companies_table),
                also_known_names = COALESCE($6, also_known_names),
                recent_bols = COALESCE($7::jsonb, recent_bols),
                carriers_per_country = COALESCE($8::jsonb, carriers_per_country),
                last_updated_at = NOW()
            WHERE supplier_slug = $9
            """,
            competitor.get("supplier_name_cn"),
            competitor.get("city") or extract_city_from_address(address),
            time_series if time_series is not None else None,
            trend_yoy,
            companies_table if companies_table is not None else None,
            list_or_none(competitor.get("also_known_names")),
            recent_bols if recent_bols is not None else None,
            carriers_per_country if carriers_per_country is not None else None,
            supplier_slug,
        )
    except Exception as e:
        logger.warning(f"[Competitors] Cached competitor enrich upsert failed for {supplier_slug}: {e}")


async def get_visible_competitor_slugs(
    *,
    conn,
    visible_limit: int,
) -> set[str]:
    # Frontend visibility: show ALL hydrated competitors regardless of HS overlap.
    # Onboarding/ingest hydrates only tenant-relevant rows into bol_competitors, and
    # some of them carry adjacent HS codes (not the tenant's confirmed set). A strict
    # overlap filter silently hides them.
    base_sql = (
        "SELECT supplier_slug FROM bol_competitors "
        "ORDER BY threat_score DESC NULLS LAST, matching_shipments DESC NULLS LAST"
    )
    # visible_limit < 0 is the entitlements sentinel for "unlimited" — omit LIMIT.
    if visible_limit is None or visible_limit < 0:
        rows = await conn.fetch(base_sql)
    else:
        rows = await conn.fetch(base_sql + " LIMIT $1", visible_limit)
    return {r["supplier_slug"] for r in rows}
