"""
Public Storefront Router
========================
Unauthenticated endpoints for buyer-facing storefront access.
Mirrors public_deal_room_router.py for rate-limit + connection patterns.

URL shape: /api/crm/public/storefront/{seller_slug} where seller_slug == db_name.
No share token, no analytics-DB lookup — the slug is the tenant DB.
"""

import json
import logging
import re
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/storefront")


# Validates the slug as a tenant db_name. Same regex used by service_core.db.
_DB_NAME_RE = re.compile(r'^(postgres|prelude_[a-z0-9_]+)$')


# Simple in-memory rate limiter for public endpoints
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str, max_requests: int, window_seconds: int):
    """Raise 429 if client exceeds max_requests within window_seconds."""
    now = time.time()
    timestamps = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < window_seconds]
    if not _rate_limit_store[client_ip]:
        del _rate_limit_store[client_ip]
    if len(_rate_limit_store.get(client_ip, [])) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests")
    _rate_limit_store[client_ip].append(now)


def _validate_slug(seller_slug: str) -> str:
    """Validate slug is a safe tenant db_name. Raises 404 otherwise."""
    if not _DB_NAME_RE.match(seller_slug or ""):
        raise HTTPException(status_code=404, detail="Storefront not found")
    return seller_slug


class QuoteRequestPayload(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    quantity: Optional[int] = None
    message: Optional[str] = None
    product_name: str
    product_sku: Optional[str] = None
    # Email of the seller who shared this storefront link. Required: the deal
    # is attributed to this employee. If the email doesn't match anyone on the
    # tenant, the request is rejected (no silent fallback). The seller's
    # Prelude language preference is also looked up off this email to pick the
    # deal_name prefix and product name written into /crm.
    seller_email: EmailStr


def _parse_jsonb(val):
    """Decode a JSONB column into a dict. asyncpg usually returns a dict
    already, but defends against legacy string scalars."""
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    if hasattr(val, 'keys'):
        return dict(val)
    return {}


def _nz(val: Any) -> Any:
    """Return the value unchanged unless it's an empty/whitespace string,
    in which case return None. Treats blank strings as "unset" so the
    buyer page degrades the same way for "" and missing keys."""
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    return val


def _seller_display_name(company_profile: dict) -> str:
    """Phase A's `<CompanyInfoSection>` saves `companyNameEn` / `companyNameZh`,
    which `ApiClient.toSnakeCase` (deep) writes to JSONB as `company_name_en`
    / `company_name_zh`. We read the snake_case shape directly — that's
    canonical for every Phase A write."""
    if not company_profile:
        return ""
    for key in ("company_name_en", "company_name_zh"):
        v = _nz(company_profile.get(key))
        if v:
            return str(v)
    return ""


def _str_or_none(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _iso_or_none(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return _str_or_none(val)


def _decimal_to_float(val: Any) -> Any:
    """JSONB price_range may carry Decimals after asyncpg decode in some
    setups. Cast for JSON serialization."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return {k: _decimal_to_float(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_decimal_to_float(v) for v in val]
    return val


def _build_hero_stats(company_profile: dict, factory_details: dict) -> dict:
    """Phase A canonical reads only — JSONB stores snake_case (deep) because
    `ApiClient.toSnakeCase` runs on every payload. We deliberately do NOT
    fall back to legacy wizard keys (`year_established`, `employees`,
    `annual_capacity`); a tenant that hasn't filled the new
    `<CompanyInfoSection>` form should surface as empty on the buyer page,
    not leak data the seller can't see in the current UI."""
    return {
        "yearFounded": _str_or_none(_nz(company_profile.get("year_founded"))),
        "staff": _str_or_none(_nz(company_profile.get("staff"))),
        "capacity": _str_or_none(_nz(factory_details.get("capacity"))),
        "exportShare": _str_or_none(_nz(company_profile.get("export_share"))),
    }


def _build_key_facts(factory_details: dict) -> dict:
    """Phase A canonical reads only — `<BusinessTermsSection>` writes to
    `factory_details.terms.{moq, leadTime, samplePolicy, shipping, payment}`,
    which becomes `factory_details.terms.{moq, lead_time, sample_policy, ...}`
    in JSONB after deep `toSnakeCase`. We do NOT fall back to the flat
    legacy shape — a tenant that hasn't filled the new form surfaces as
    empty on the buyer page."""
    terms = factory_details.get("terms")
    if not isinstance(terms, dict):
        terms = {}
    return {
        "moq": _str_or_none(_nz(terms.get("moq"))),
        "leadTime": _str_or_none(_nz(terms.get("lead_time"))),
        "samplePolicy": _str_or_none(_nz(terms.get("sample_policy"))),
        "shipping": _str_or_none(_nz(terms.get("shipping"))),
        "payment": _str_or_none(_nz(terms.get("payment"))),
    }


def _build_contact(company_profile: dict) -> dict:
    """Public contact card — privacy gate: omit email + phone."""
    contact = company_profile.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}
    languages = contact.get("languages") or []
    if not isinstance(languages, list):
        languages = []
    return {
        "name": _str_or_none(_nz(contact.get("name"))),
        "title": _str_or_none(_nz(contact.get("title"))),
        "languages": [str(l) for l in languages if l],
    }


def _build_factory_photo_url(factory_details: dict) -> Optional[str]:
    """Phase A's `<FactoryImagesSection>` writes `photoUrls`, which JSONB
    stores as `photo_urls` after `toSnakeCase`. We read only the snake
    form — the camelCase reads in the original dev code never matched
    anything because every payload passes through the case transform."""
    photos = factory_details.get("photo_urls")
    if isinstance(photos, list) and photos:
        return _str_or_none(_nz(photos[0]))
    return None


def _build_certifications(rows) -> list:
    """Active-only, no email filter (tenant-wide). No documentUrl on the
    public page — privacy gate."""
    out = []
    for r in rows:
        out.append({
            "certId": str(r["cert_id"]),
            "certType": _str_or_none(r["cert_type"]),
            "certNumber": _str_or_none(r["cert_number"]),
            "issuingBody": _str_or_none(r["issuing_body"]),
            "expiryDate": _iso_or_none(r["expiry_date"]),
            "notes": _str_or_none(r["notes"]),
        })
    return out


def _build_products(rows) -> list:
    out = []
    for r in rows:
        specs = _parse_jsonb(r["specs"]) or {}
        price_range = _parse_jsonb(r["price_range"])
        price_range = _decimal_to_float(price_range) if price_range else None
        out.append({
            "productId": str(r["product_id"]),
            "name": r["name"],
            "description": _str_or_none(r["description"]),
            "specs": specs if isinstance(specs, dict) else {},
            "imageUrl": _str_or_none(r["image_url"]),
            "moq": int(r["moq"]) if r["moq"] is not None else None,
            "priceRange": price_range,
            "hsCode": _str_or_none(r["hs_code"]),
            "publishedAt": _iso_or_none(r["published_at"]),
        })
    return out


@router.get("/{seller_slug}")
async def get_public_storefront(seller_slug: str, request: Request):
    """Public buyer view of a seller's storefront. English-only by design —
    the seller's Prelude language drives the deal_name (see POST below), not
    anything the buyer sees here.

    Products and certifications are scoped to the seller named in the
    ``?seller=`` query param. A tenant DB can host multiple users
    (e.g. james@... and aoxue@... both on `postgres`); each user's shared
    link must show only their own catalog, mirroring how the seller-side
    `已上架` view scopes by signed-in email. Without `?seller=` we have no
    employee context, so we return an empty catalog and empty cert list —
    the FE already shows an "incomplete share" warning in that case.
    """
    _check_rate_limit(
        request.client.host if request.client else "unknown",
        max_requests=30,
        window_seconds=60,
    )
    _validate_slug(seller_slug)

    raw_seller = request.query_params.get("seller")
    seller_email = (raw_seller or "").strip().lower() or None

    pm = get_pool_manager()
    try:
        async with pm.acquire(seller_slug) as conn:
            sub_row = await conn.fetchrow(
                "SELECT company_profile, factory_details "
                "FROM tenant_subscription LIMIT 1"
            )
            if seller_email:
                cert_rows = await conn.fetch(
                    "SELECT cert_id, cert_type, cert_number, issuing_body, "
                    "expiry_date, notes "
                    "FROM factory_certifications "
                    "WHERE status = 'active' AND LOWER(email) = $1 "
                    "ORDER BY expiry_date DESC NULLS LAST",
                    seller_email,
                )
                product_rows = await conn.fetch(
                    "SELECT product_id, name, description, specs, image_url, "
                    "moq, price_range, hs_code, published_at "
                    "FROM product_catalog "
                    "WHERE status = 'live' AND LOWER(email) = $1 "
                    "ORDER BY published_at DESC NULLS LAST",
                    seller_email,
                )
            else:
                # No `?seller=` — incomplete share link. Buyer FE already shows
                # the "incomplete share" warning + disables Quote; surface
                # empty catalog/certs to match.
                cert_rows = []
                product_rows = []
    except Exception as e:
        # asyncpg raises InvalidCatalogNameError when DB does not exist.
        logger.info(f"Storefront lookup failed for slug={seller_slug}: {e}")
        raise HTTPException(status_code=404, detail="Storefront not found")

    company_profile = _parse_jsonb(sub_row["company_profile"]) if sub_row else {}
    factory_details = _parse_jsonb(sub_row["factory_details"]) if sub_row else {}

    seller_name = _seller_display_name(company_profile) or seller_slug

    return {
        "sellerName": seller_name,
        "sellerSlug": seller_slug,
        "sellerLogoUrl": _str_or_none(_nz(company_profile.get("logo_url"))),
        "factoryPhotoUrl": _build_factory_photo_url(factory_details),
        "tagline": _str_or_none(_nz(company_profile.get("tagline"))),
        "heroStats": _build_hero_stats(company_profile, factory_details),
        "keyFacts": _build_key_facts(factory_details),
        "certifications": _build_certifications(cert_rows),
        "contact": _build_contact(company_profile),
        "products": _build_products(product_rows),
    }


@router.post("/{seller_slug}/quote-request")
async def create_quote_request(seller_slug: str, payload: QuoteRequestPayload, request: Request):
    """Buyer submits a quote request against a seller's storefront.

    One tenant-DB transaction:
      1. find-or-create customer (by personnel.email)
      2. insert deals row (room_status='quote_requested')
      3. insert interaction_details row (type='quote_request')
    """
    _check_rate_limit(
        request.client.host if request.client else "unknown",
        max_requests=5,
        window_seconds=60,
    )
    _validate_slug(seller_slug)

    email = payload.email.strip().lower()
    buyer_name = (payload.name or "").strip()
    # clients.name shows up in the deals list ("线索" column). Prefer the
    # buyer-supplied company, fall back to their name, then the full email.
    # Never use just the email domain — "gmail.com" tells the seller nothing.
    company_name = (payload.company or "").strip() or buyer_name or email
    full_name = buyer_name or email

    pm = get_pool_manager()
    try:
        async with pm.acquire(seller_slug) as conn:
            # Attribute the deal to the seller who shared the link (passed via
            # the storefront URL's `seller` query param → seller_email here).
            # Strict: the email must match an employee on the tenant; no fallback.
            # NOT NULL on deals.employee_id and interaction_details.employee_id.
            employee_id = await conn.fetchval(
                "SELECT employee_id FROM employee_info "
                "WHERE LOWER(email) = LOWER($1) LIMIT 1",
                payload.seller_email,
            )
            if employee_id is None:
                raise HTTPException(
                    status_code=404,
                    detail="Seller not found on this storefront",
                )

            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT p.client_id "
                    "FROM personnel p "
                    "WHERE LOWER(p.email) = $1 AND p.client_id IS NOT NULL "
                    "ORDER BY p.is_primary DESC NULLS LAST, p.created_at ASC "
                    "LIMIT 1",
                    email,
                )
                if existing:
                    client_id = existing["client_id"]
                else:
                    client_row = await conn.fetchrow(
                        "INSERT INTO clients (name, source, created_at, updated_at) "
                        "VALUES ($1, 'storefront_quote_request', NOW(), NOW()) "
                        "RETURNING client_id",
                        company_name,
                    )
                    client_id = client_row["client_id"]

                    # Personnel has UNIQUE(full_name, company_name); skip on conflict.
                    await conn.execute(
                        "INSERT INTO personnel ("
                        "  first_name, last_name, full_name, company_name, "
                        "  source, email, client_id, is_primary, created_at, updated_at"
                        ") VALUES ('', '', $1, $2, 'storefront_quote_request', $3, $4, true, NOW(), NOW()) "
                        "ON CONFLICT (full_name, company_name) DO NOTHING",
                        full_name, company_name, email, client_id,
                    )

                # Look up the seller's Prelude language so 商机名称 in /crm
                # reads in whichever language the seller has chosen there.
                # user_profiles lives in the shared analytics DB; read-only
                # lookup, no schema change.
                seller_locale = ""
                try:
                    analytics_pool = await pm.get_analytics_pool()
                    loc_row = await analytics_pool.fetchrow(
                        "SELECT preferred_locale FROM user_profiles "
                        "WHERE LOWER(email) = LOWER($1) LIMIT 1",
                        payload.seller_email,
                    )
                    if loc_row and loc_row["preferred_locale"]:
                        seller_locale = str(loc_row["preferred_locale"])
                except Exception as e:
                    logger.warning(
                        f"Failed to read preferred_locale for {payload.seller_email}: {e}"
                    )

                is_zh = seller_locale.lower().startswith("zh")
                deal_name_prefix = "报价：" if is_zh else "Quote: "

                # product_catalog stores a single-language name today; the
                # buyer page passes that name verbatim. No bilingual lookup.
                deal_row = await conn.fetchrow(
                    "INSERT INTO deals ("
                    "  deal_name, product_name, employee_id, client_id, "
                    "  quantity, room_status, created_at, updated_at"
                    ") VALUES ($1, $2, $3, $4, $5, 'quote_requested', NOW(), NOW()) "
                    "RETURNING deal_id",
                    f"{deal_name_prefix}{payload.product_name}",
                    payload.product_name,
                    employee_id,
                    client_id,
                    payload.quantity,
                )
                deal_id = deal_row["deal_id"]

                content = json.dumps({
                    "email": email,
                    "name": buyer_name or None,
                    "company": payload.company or None,
                    "quantity": payload.quantity,
                    "message": payload.message or None,
                    "productName": payload.product_name,
                    "productSku": payload.product_sku,
                })
                await conn.execute(
                    "INSERT INTO interaction_details ("
                    "  customer_id, deal_id, employee_id, type, content, source, created_at"
                    ") VALUES ($1, $2, $3, 'quote_request', $4, 'storefront', NOW())",
                    client_id, deal_id, employee_id, content,
                )

            logger.info(
                f"STOREFRONT_QUOTE: slug={seller_slug} deal_id={deal_id} "
                f"client_id={client_id} email={email} product={payload.product_name!r}"
            )
            return {"success": True, "dealId": deal_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating storefront quote request for slug={seller_slug}: {e}")
        # Hide DB internals from the buyer; treat unknown DB as 404.
        raise HTTPException(status_code=500, detail="Failed to submit quote request")
