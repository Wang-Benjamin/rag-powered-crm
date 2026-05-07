"""Core lead-creation pipeline for BoL/ImportYeti companies."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from importyeti.clients import internal_bol_client
from utils.background_tasks import fire_tracked
from importyeti.domain.transformers import normalize_for_dedup, parse_city_state
from importyeti.services.lead_enrichment import enrich_lead_contact
from data.repositories.lead_repository import LeadRepository
from service_core.activity import ActivityLogger
from config.constants import LeadSource
from database.queries import get_employee_id_by_email

logger = logging.getLogger(__name__)


async def _generate_condensed_for_lead(
    db_name: str,
    lead_id: str,
    import_context: dict | None,
    supplier_context: dict | None,
    bol_detail_context: dict | None,
):
    """Background task: generate condensed AI taglines (both locales) after lead creation.

    Only the condensed insight is eager — the full aiActionBrief is generated
    lazily on first detail-view open to keep pipeline LLM costs low.
    """
    import json
    try:
        from importyeti.domain.insight import generate_condensed_insight
        from service_core.db import get_pool_manager

        condensed_zh, condensed_en = await asyncio.gather(
            generate_condensed_insight(import_context, supplier_context, bol_detail_context, locale="zh-CN"),
            generate_condensed_insight(import_context, supplier_context, bol_detail_context, locale="en"),
        )

        if not condensed_zh and not condensed_en:
            return

        pm = get_pool_manager()
        async with pm.acquire(db_name) as conn:
            row = await conn.fetchrow(
                "SELECT bol_detail_context FROM leads WHERE lead_id = $1", lead_id,
            )
            if not row:
                return
            current = row["bol_detail_context"]
            if isinstance(current, str):
                current = json.loads(current)
            if not isinstance(current, dict):
                return

            changed = False
            if condensed_zh and not current.get("aiInsightCondensed_zh-CN"):
                current["aiInsightCondensed_zh-CN"] = condensed_zh
                current["aiInsightCondensed"] = condensed_zh
                changed = True
            if condensed_en and not current.get("aiInsightCondensed_en"):
                current["aiInsightCondensed_en"] = condensed_en
                if not current.get("aiInsightCondensed"):
                    current["aiInsightCondensed"] = condensed_en
                changed = True

            if changed:
                # Pass dict; the pool's JSONB codec (encoder=json.dumps) handles
                # serialization. Passing json.dumps(current) here would double-encode
                # into a JSONB string.
                await conn.execute(
                    "UPDATE leads SET bol_detail_context = $1::jsonb WHERE lead_id = $2",
                    current, lead_id,
                )
    except Exception as e:
        logger.warning(f"Background condensed insight generation failed for lead {lead_id}: {e}")


async def add_slugs_to_pipeline(
    conn,
    user: Dict[str, Any],
    auth_token: str,
    slugs: List[str],
    prefetched_companies: Dict[str, Dict] = None,
) -> Dict[str, Any]:
    """
    Core lead-creation pipeline extracted from the add_to_pipeline router handler.

    - Fetches each slug from the 8007 BoL cache (skipped when prefetched_companies provided)
    - Pre-checks existing leads by HS code to dedupe
    - Creates new leads via LeadRepository with import_context / supplier_context / bol_detail_context
    - Assigns existing leads to the current employee on duplicate

    Trial gating is handled in the HTTP wrapper; this helper does not re-check it.

    When `prefetched_companies` is provided (slug→company dict), Phase 1 skips
    per-slug cache reads and uses the in-memory data directly. The kickoff handler
    passes the search_cache result here to avoid ~100 individual get_company calls.
    """
    user_email = user.get("email", "unknown")

    lead_repo = LeadRepository()
    created = 0
    assigned = 0
    errors: List[Dict[str, Any]] = []
    slugs = list(dict.fromkeys(slugs))  # dedupe, preserve order

    # Resolve employee_id for assigning leads to the current user
    employee_id = None
    try:
        employee_id = await get_employee_id_by_email(conn, user_email)
    except Exception as e:
        logger.warning(f"Could not resolve employee_id for {user_email}: {e}")

    # --- Phase 1: Pre-fetch all cached companies -------------------------
    # When prefetched_companies is provided, skip individual cache reads
    companies_by_slug: Dict[str, Dict] = {}
    all_hs_codes: set = set()
    if prefetched_companies:
        for slug in slugs:
            company = prefetched_companies.get(slug)
            if not company:
                errors.append({"slug": slug, "error": "Not found in pre-fetched data"})
                continue
            companies_by_slug[slug] = company
            for code in (company.get("hs_codes") or []):
                if code:
                    all_hs_codes.add(str(code))
    else:
        sem = asyncio.Semaphore(10)

        async def _fetch_one(slug: str):
            async with sem:
                try:
                    company = await internal_bol_client.get_company(slug, auth_token=auth_token)
                    if not company:
                        return (slug, None, "Not found in cache")
                    return (slug, company, None)
                except Exception as e:
                    logger.warning(f"Failed to fetch cached company {slug}: {e}")
                    return (slug, None, str(e))

        results = await asyncio.gather(*[_fetch_one(s) for s in slugs])
        for slug, company, error in results:
            if error:
                errors.append({"slug": slug, "error": error})
                continue
            companies_by_slug[slug] = company
            for code in (company.get("hs_codes") or []):
                if code:
                    all_hs_codes.add(str(code))

    # --- Phase 2: Pre-check existing leads by HS code --------------------
    existing_leads: set = set()
    if companies_by_slug and all_hs_codes:
        try:
            rows = await conn.fetch(
                "SELECT company, location FROM leads "
                "WHERE import_context->'hsCodes' ?| $1::text[]",
                list(all_hs_codes),
            )
            existing_leads = {(normalize_for_dedup(r["company"]), normalize_for_dedup(r["location"])) for r in rows}
            logger.info(f"Pre-check found {len(existing_leads)} existing leads for HS codes {list(all_hs_codes)}")
        except Exception as e:
            logger.warning(f"Pre-check query failed, falling back to insert: {e}")

    # --- Phase 3: Create leads, skipping duplicates ----------------------
    for slug in slugs:
        company = companies_by_slug.get(slug)
        if not company:
            continue  # already recorded as error in phase 1

        try:
            # Build import_context from PowerQuery data (available for all companies)
            import_context = {
                "totalShipments": company.get("company_total_shipments"),
                "matchingShipments": company.get("matching_shipments"),
                "mostRecentShipment": company.get("most_recent_shipment"),
                "topPorts": company.get("ports_of_entry"),
                "topProducts": company.get("product_descriptions"),
                "hsCodes": company.get("hs_codes"),
                "totalSuppliers": company.get("total_suppliers"),
                "topSuppliers": company.get("top_suppliers"),
            }

            # Build supplier_context from deep enrichment data (null if not enriched)
            supplier_context = None
            bol_detail_context = None
            if company.get("enrichment_status") == "detail_enriched" and company.get("supplier_breakdown"):
                suppliers = []
                for s in company["supplier_breakdown"]:
                    s12 = s.get("shipments_12m", 0)
                    s24 = s.get("shipments_12_24m", 0)
                    trend = round((s12 - s24) / s24 * 100, 1) if s24 > 0 else 0
                    suppliers.append({
                        "name": s.get("supplier_name"),
                        "country": s.get("country"),
                        "share": s.get("shipments_percents_company", 0),
                        "shipments12M": s12,
                        "shipments1224M": s24,
                        "trend": trend,
                        "weightKg": s.get("weight_kg", 0),
                        "teu": s.get("teu", 0),
                    })
                supplier_context = {
                    "suppliers": suppliers,
                    "enrichedAt": datetime.now(timezone.utc).isoformat(),
                    "bolCompanySlug": slug,
                }

                # Build bol_detail_context — prefer pre-computed values from enrichment cache
                cached_signals = company.get("scoring_signals")
                if cached_signals:
                    # Use pre-computed values from enrichment
                    cn_pct = company.get("derived_china_concentration_12m") or company.get("derived_china_concentration")
                    growth = company.get("derived_growth_12m_pct")
                    ts = company.get("time_series") or {}
                else:
                    # Fallback: recompute (for companies enriched before scoring_signals were persisted)
                    from importyeti.domain.transformers import compute_china_concentration, compute_growth_12m
                    from importyeti.domain.scoring import (
                        _signal_1_reorder_window, _signal_2_supplier_diversification,
                        _signal_3_competitive_displacement, _signal_4_volume_fit,
                        _signal_5_recency_activity, _signal_6_hs_relevance,
                        _signal_7_shipment_scale, _signal_8_switching_velocity,
                        _signal_9_buyer_growth, _signal_10_supply_chain_vulnerability,
                        _signal_11_order_consistency,
                    )
                    from importyeti.domain.transformers import (
                        build_company_data, build_query_data,
                        compute_china_concentration_12m, compute_avg_order_cycle_days,
                        compute_supplier_company_yoy, compute_supplier_hhi,
                        compute_order_regularity_cv,
                    )

                    ts = company.get("time_series") or {}
                    cn = compute_china_concentration(ts)
                    cn_12m = compute_china_concentration_12m(ts)
                    growth = compute_growth_12m(ts)

                    avg_cycle = compute_avg_order_cycle_days(ts)
                    if avg_cycle:
                        import_context["avgOrderCycleDays"] = round(avg_cycle, 1)
                    yoy = compute_supplier_company_yoy(ts)
                    hhi = compute_supplier_hhi(company["supplier_breakdown"])
                    cv = compute_order_regularity_cv(ts)
                    total_suppliers = company.get("total_suppliers") or len(company["supplier_breakdown"])

                    c_data = build_company_data(
                        most_recent_shipment=company.get("most_recent_shipment"),
                        total_suppliers=total_suppliers,
                        company_total_shipments=company.get("company_total_shipments"),
                        supplier_breakdown=company["supplier_breakdown"],
                        avg_order_cycle_days=avg_cycle,
                        matching_shipments=company.get("matching_shipments"),
                        weight_kg=company.get("weight_kg"),
                        teu=company.get("teu"),
                        derived_growth_12m_pct=growth,
                        derived_supplier_hhi=hhi,
                        derived_order_regularity_cv=cv,
                    )
                    q_data = build_query_data(
                        china_concentration=cn_12m if cn_12m is not None else cn,
                        cn_dominated_hs_code=company.get("cn_dominated_hs_code", False),
                        supplier_company_yoy=yoy,
                    )

                    cached_signals = {
                        "reorderWindow": {"points": round(_signal_1_reorder_window(c_data), 1), "max": 20},
                        "supplierDiversification": {"points": round(_signal_2_supplier_diversification(c_data, q_data), 1), "max": 15},
                        "competitiveDisplacement": {"points": round(_signal_3_competitive_displacement(c_data, q_data), 1), "max": 10},
                        "volumeFit": {"points": round(_signal_4_volume_fit(c_data), 1), "max": 12},
                        "recencyActivity": {"points": round(_signal_5_recency_activity(c_data, q_data), 1), "max": 13},
                        "hsRelevance": {"points": round(_signal_6_hs_relevance(c_data), 1), "max": 10},
                        "shipmentScale": {"points": round(_signal_7_shipment_scale(c_data), 1), "max": 5},
                        "switchingVelocity": {"points": round(_signal_8_switching_velocity(c_data), 1), "max": 3},
                        "buyerGrowth": {"points": round(_signal_9_buyer_growth(c_data), 1), "max": 5},
                        "supplyChainVulnerability": {"points": round(_signal_10_supply_chain_vulnerability(c_data), 1), "max": 4},
                        "orderConsistency": {"points": round(_signal_11_order_consistency(c_data), 1), "max": 3},
                    }
                    cn_pct = cn_12m if cn_12m is not None else cn

                # Convert recent_bols from snake_case to camelCase for frontend
                raw_bols = company.get("recent_bols") or []
                camel_bols = []
                for b in raw_bols:
                    camel_bols.append({
                        "dateFormatted": b.get("date_formatted", ""),
                        "productDescription": b.get("Product_Description") or b.get("product_description", ""),
                        "hsCode": b.get("HS_Code") or b.get("hs_code", ""),
                        "quantity": str(b.get("Quantity") or b.get("quantity", "")),
                        "quantityUnit": b.get("Quantity_Unit") or b.get("quantity_unit", ""),
                        "weightInKg": str(b.get("Weight_in_KG") or b.get("weight_in_kg", "")),
                        "teu": str(b.get("TEU") or b.get("teu", "")),
                        "shipperName": b.get("Shipper_Name") or b.get("shipper_name", ""),
                        "consigneeName": b.get("Consignee_Name") or b.get("consignee_name", ""),
                        "country": b.get("Country") or b.get("country", ""),
                        "countryCode": b.get("country_code", ""),
                    })

                # Convert time_series values from snake_case to camelCase
                camel_ts = {}
                for date_key, data in ts.items():
                    camel_ts[date_key] = {
                        "shipments": data.get("shipments", 0),
                        "weight": data.get("weight", 0),
                        "teu": data.get("teu", 0),
                        "chinaShipments": data.get("china_shipments", 0),
                        "chinaWeight": data.get("china_weight", 0),
                        "chinaTeu": data.get("china_teu", 0),
                    }

                bol_detail_context = {
                    "timeSeries": camel_ts,
                    "recentBols": camel_bols,
                    "chinaConcentration": round(cn_pct, 1) if cn_pct is not None else None,
                    "growth12mPct": round(growth, 1) if growth is not None else None,
                    "aiActionBrief": company.get("ai_action_brief"),
                    "scoringSignals": cached_signals,
                }

            # Build location from cached address fields
            location_parts = [
                p for p in [company.get("city"), company.get("state")]
                if p
            ]
            if location_parts:
                location = ", ".join(location_parts)
            else:
                location = parse_city_state(company.get("address") or "")

            company_name = company.get("company_name")
            lead_location = location or "Unknown"

            # If duplicate detected in pre-check, assign to current user
            if (normalize_for_dedup(company_name), normalize_for_dedup(lead_location)) in existing_leads:
                if employee_id:
                    try:
                        row = await conn.fetchrow(
                            "SELECT lead_id FROM leads WHERE LOWER(TRIM(company)) = $1 AND LOWER(TRIM(location)) = $2",
                            normalize_for_dedup(company_name), normalize_for_dedup(lead_location),
                        )
                        if row:
                            await conn.execute(
                                "INSERT INTO employee_lead_links (employee_id, lead_id, matched_by, status) "
                                "VALUES ($1, $2, 'importyeti_pipeline', 'active') "
                                "ON CONFLICT (employee_id, lead_id) DO NOTHING",
                                employee_id, row["lead_id"],
                            )
                    except Exception as link_err:
                        logger.warning(f"Failed to assign existing lead to employee: {link_err}")
                assigned += 1
                continue

            # Create lead via LeadRepository
            lead_data = {
                "company": company_name,
                "location": lead_location,
                "website": company.get("website"),
                "source": LeadSource.IMPORTYETI.value,
                "score": company.get("enriched_score") or company.get("quick_score") or 0,
                "import_context": import_context,
                "supplier_context": supplier_context,
                "bol_detail_context": bol_detail_context,
            }

            lead_id = await lead_repo.create_lead(
                conn, lead_data, user_id=user_email,
                user_email=user_email, auth_token=auth_token,
            )
            if lead_id:
                created += 1
                await ActivityLogger.log("enrich", "lead", str(lead_id), {"status": "success", "service": "leadgen", "source": "importyeti", "company": company_name})
                # Fire background condensed insight generation for deep-enriched leads
                if bol_detail_context and bol_detail_context.get("scoringSignals"):
                    fire_tracked("generate_condensed", lambda _db=user.get("db_name", "postgres"), _lid=lead_id, _ic=import_context, _sc=supplier_context, _bc=bol_detail_context: _generate_condensed_for_lead(
                        _db, str(_lid), _ic, _sc, _bc,
                    ), retries=1, context={"lead_id": str(lead_id), "company": company_name})
                # Assign lead to current user via employee_lead_links
                if employee_id:
                    try:
                        await conn.execute(
                            "INSERT INTO employee_lead_links (employee_id, lead_id, matched_by, status) "
                            "VALUES ($1, $2::uuid, 'importyeti_pipeline', 'active') "
                            "ON CONFLICT (employee_id, lead_id) DO NOTHING",
                            employee_id, lead_id,
                        )
                    except Exception as link_err:
                        logger.warning(f"Failed to link lead {lead_id} to employee {employee_id}: {link_err}")
                # Check if ImportYeti already has a personal contact before using Apollo
                fire_tracked("enrich_lead_contact", lambda _db=user.get("db_name", "postgres"), _lid=lead_id, _cn=company_name, _w=company.get("website"), _ci=company.get("city"), _st=company.get("state"), _co=company.get("country"), _ve=company.get("validated_email"), _vn=company.get("validated_contact_name"), _sl=slug, _at=auth_token: enrich_lead_contact(
                    _db, _lid, _cn, _w, _ci, _st, country=_co,
                    validated_email=_ve, validated_contact_name=_vn,
                    slug=_sl, auth_token=_at,
                ), retries=1, context={"lead_id": str(lead_id), "company": company_name})
            else:
                errors.append({"slug": slug, "error": "Lead creation returned None"})

        except Exception as e:
            err_str = str(e)
            if "unique_company_location" in err_str or "duplicate key" in err_str.lower():
                # Safety net: assign existing lead to current user
                if employee_id and company_name and lead_location:
                    try:
                        row = await conn.fetchrow(
                            "SELECT lead_id FROM leads WHERE LOWER(TRIM(company)) = $1 AND LOWER(TRIM(location)) = $2",
                            normalize_for_dedup(company_name), normalize_for_dedup(lead_location),
                        )
                        if row:
                            await conn.execute(
                                "INSERT INTO employee_lead_links (employee_id, lead_id, matched_by, status) "
                                "VALUES ($1, $2, 'importyeti_pipeline', 'active') "
                                "ON CONFLICT (employee_id, lead_id) DO NOTHING",
                                employee_id, row["lead_id"],
                            )
                            logger.info(f"Assigned existing lead {row['lead_id']} to employee {employee_id}")
                    except Exception as link_err:
                        logger.warning(f"Failed to assign existing lead to employee: {link_err}")
                assigned += 1
            else:
                logger.warning(f"Failed to add {slug} to pipeline: {e}")
                errors.append({"slug": slug, "error": err_str})

    return {
        "created": created,
        "assigned": assigned,
        "total_requested": len(slugs),
        "errors": errors,
    }
