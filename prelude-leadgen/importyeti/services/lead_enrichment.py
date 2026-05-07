"""Lead contact enrichment — pre-validated email from cache + provider fallback."""

import asyncio
import logging
import os
import random
from typing import Optional

import httpx

from importyeti.domain.validation import validate_email_domain
from importyeti.clients import internal_bol_client
from importyeti.services.contact_cache_writer import save_contact_to_cache
from data.repositories.personnel_repository import PersonnelRepository

# Provider selection — controlled by ENRICHMENT_PROVIDER env var
_PROVIDER = os.getenv("ENRICHMENT_PROVIDER", "lemlist").lower()
if _PROVIDER == "lemlist":
    from lemlist.client import LemlistClient as _EnrichClient, LemlistConfig as _EnrichConfig
    _KEY_VAR = "LEMLIST_API_KEY"
    _URL_DEFAULT = "https://api.lemlist.com/api"
else:
    from apollo_io.client import ApolloClient as _EnrichClient
    from apollo_io.schemas import ApolloConfig as _EnrichConfig
    _KEY_VAR = "APOLLO_API_KEY"
    _URL_DEFAULT = "https://api.apollo.io"

logger = logging.getLogger(__name__)

# Values that look like a name field but actually mean "no name available".
# Keep in sync with the outreach prompt's sentinel list so downstream greeting
# logic can fall back to "Hi," cleanly.
_JUNK_NAME_TOKENS = {"", "null", "none", "unknown", "n/a", "na"}


def _normalize_contact_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    trimmed = name.strip()
    if trimmed.lower() in _JUNK_NAME_TOKENS:
        return None
    return trimmed


async def check_company_contact(
    slug: str,
    company_name: str,
    website: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    validated_email: Optional[str] = None,
    validated_contact_name: Optional[str] = None,
    auth_token: str = "",
) -> dict:
    """Pre-lead contact check — no lead_id needed.

    1. If validated_email passes domain check -> return immediately
    2. Fall back to Apollo company-level lookup
    3. Write validated_* contact back to 8007 cache via save_contact_to_cache
    4. Return {has_contact, email, contact_name}
    """
    lead_country = country or "US"

    # 1. Pre-validated email from CSV ingestion or prior Apollo pass
    if validated_email:
        valid, _ = validate_email_domain(validated_email, lead_state=state, lead_country=lead_country)
        if valid:
            return {
                "has_contact": True,
                "email": validated_email,
                "contact_name": validated_contact_name,
            }

    # 2. Provider fallback (Lemlist or Apollo, per ENRICHMENT_PROVIDER)
    # Missing API key or call-level exception is treated as transient — we
    # return no_contact without persisting so the buyer isn't permanently hidden.
    api_key = os.getenv(_KEY_VAR)
    if not api_key:
        logger.warning(f"{_KEY_VAR} not set — skipping contact check for {slug}")
        return {"has_contact": False, "email": None, "contact_name": None}

    config = _EnrichConfig(
        api_key=api_key,
        base_url=os.getenv("LEMLIST_BASE_URL", _URL_DEFAULT) if _PROVIDER == "lemlist"
            else os.getenv("APOLLO_BASE_URL", _URL_DEFAULT),
        timeout_seconds=int(os.getenv("LEMLIST_TIMEOUT" if _PROVIDER == "lemlist" else "APOLLO_TIMEOUT", "30")),
    )

    location_parts = [p for p in [city, state] if p]
    location = ", ".join(location_parts) if location_parts else None

    company_dict = {
        "source": "google_maps",
        "company_name": company_name,
        "location": location or "",
        "website": website or "",
    }

    enriched = None
    for attempt in range(2):
        try:
            async with _EnrichClient(config) as client:
                enriched = await client.enrich_company_emails(
                    company_ids=[slug],
                    companies=[company_dict],
                )
            break  # success
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == 0:
                await asyncio.sleep(2.0 + random.uniform(0, 1))
                continue
            logger.warning(f"Contact check failed for {slug} after retry: {e}")
            return {"has_contact": False, "email": None, "contact_name": None}
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                logger.warning(f"Contact check failed for {slug}: {e}")
                return {"has_contact": False, "email": None, "contact_name": None}
            if attempt == 0:
                await asyncio.sleep(2.0 + random.uniform(0, 1))
                continue
            logger.warning(f"Contact check failed for {slug} after retry: {e}")
            return {"has_contact": False, "email": None, "contact_name": None}
        except Exception as e:
            logger.warning(f"Contact check failed for {slug}: {e}")
            return {"has_contact": False, "email": None, "contact_name": None}

    # Provider answered — evaluate the response.
    if enriched and enriched[0].get("contact_email"):
        contact_email = enriched[0]["contact_email"]
        contact_name = enriched[0].get("contact_name")
        contact_title = enriched[0].get("contact_title") or enriched[0].get("title")

        # Validate Apollo email
        valid, _ = validate_email_domain(contact_email, lead_state=state, lead_country=lead_country)
        if valid:
            try:
                await save_contact_to_cache(
                    slug,
                    email=contact_email,
                    name=contact_name,
                    title=contact_title,
                    auth_token=auth_token,
                )
            except Exception as e:
                logger.warning(f"Failed to write apollo contact for {slug}: {e}")
            return {
                "has_contact": True,
                "email": contact_email,
                "contact_name": contact_name,
            }

    return {"has_contact": False, "email": None, "contact_name": None}


async def enrich_lead_contact(
    db_name: str, lead_id: str, company_name: str,
    website: Optional[str], city: Optional[str], state: Optional[str],
    country: Optional[str] = None,
    validated_email: Optional[str] = None,
    validated_contact_name: Optional[str] = None,
    slug: Optional[str] = None,
    auth_token: str = "",
):
    """Use pre-validated email from cache if available; fall back to Apollo otherwise."""
    if slug:
        result = await check_company_contact(
            slug=slug, company_name=company_name,
            website=website, city=city, state=state, country=country,
            validated_email=validated_email,
            validated_contact_name=validated_contact_name,
            auth_token=auth_token,
        )
        if result["has_contact"]:
            await _save_personnel(db_name, lead_id, company_name, result["email"], result["contact_name"])
        return

    # Legacy path — no slug available (shouldn't happen for CSV path)
    lead_country = country or "US"
    if validated_email:
        valid, _ = validate_email_domain(validated_email, lead_state=state, lead_country=lead_country)
        if valid:
            await _save_personnel(db_name, lead_id, company_name, validated_email, validated_contact_name)
            return
    await enrich_lead_via_apollo(db_name, lead_id, company_name, website, city, state, country=country)


async def _save_personnel(
    db_name: str, lead_id: str, company_name: str,
    email: str, name: Optional[str],
):
    """Create a personnel record from a validated email."""
    from service_core.db import get_pool_manager
    pm = get_pool_manager()
    async with pm.acquire(db_name) as conn:
        cleaned = _normalize_contact_name(name)
        name_parts = cleaned.split(None, 1) if cleaned else []
        first_name = name_parts[0] if name_parts else email.split("@")[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "Unknown"
        full_name = cleaned if cleaned else "Unknown Contact"
        personnel_repo = PersonnelRepository()
        try:
            await personnel_repo.create_personnel(conn, {
                "lead_id": lead_id,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "email": email,
                "company_name": company_name,
                "source": "importyeti",
            })
        except Exception as pe:
            logger.warning(f"Personnel creation failed for {company_name}: {pe}")


async def enrich_lead_via_apollo(
    db_name: str, lead_id: str, company_name: str,
    website: Optional[str], city: Optional[str], state: Optional[str],
    country: Optional[str] = None,
):
    """Background task: look up company, find a decision maker,
    update the lead's email, and create a personnel record.
    Acquires its own DB connection since the request connection is released."""
    try:
        api_key = os.getenv(_KEY_VAR)
        if not api_key:
            return

        config = _EnrichConfig(
            api_key=api_key,
            base_url=os.getenv("LEMLIST_BASE_URL", _URL_DEFAULT) if _PROVIDER == "lemlist"
                else os.getenv("APOLLO_BASE_URL", _URL_DEFAULT),
            timeout_seconds=int(os.getenv("LEMLIST_TIMEOUT" if _PROVIDER == "lemlist" else "APOLLO_TIMEOUT", "30")),
        )

        # Build location string for matching (city, state)
        loc_parts = [p for p in [city, state] if p]
        location = ", ".join(loc_parts) if loc_parts else ""

        # Use source='google_maps' to trigger the multi-strategy
        # normalized name search inside enrich_company_emails()
        company_dict = {
            "source": "google_maps",
            "company_name": company_name,
            "location": location,
            "website": website,
        }

        async with _EnrichClient(config) as client:
            enriched = await client.enrich_company_emails(
                company_ids=[lead_id],
                companies=[company_dict],
            )

        if not enriched:
            logger.info(f"Enrichment: no match for '{company_name}'")
            return

        dm = enriched[0]
        contact_email = dm.get("contact_email")
        contact_name = dm.get("contact_name")
        contact_title = dm.get("contact_title")

        if not contact_email:
            return

        # Validate email domain before saving
        lead_country = country or "US"
        valid, reason = validate_email_domain(contact_email, lead_state=state, lead_country=lead_country)
        if not valid:
            logger.info(f"Email rejected for '{company_name}': {contact_email} ({reason})")
            return

        # Acquire a fresh connection for DB writes
        from service_core.db import get_pool_manager
        pm = get_pool_manager()
        async with pm.acquire(db_name) as conn:
            # Create personnel record
            cleaned = _normalize_contact_name(contact_name)
            if cleaned:
                name_parts = cleaned.split(None, 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else "Unknown"

                personnel_repo = PersonnelRepository()
                try:
                    await personnel_repo.create_personnel(conn, {
                        "lead_id": lead_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "full_name": cleaned,
                        "email": contact_email,
                        "position": contact_title,
                        "company_name": company_name,
                        "source": _PROVIDER,
                    })
                except Exception as pe:
                    logger.warning(f"Personnel creation failed for {company_name}: {pe}")

        logger.info(f"Enriched '{company_name}': {contact_name} <{contact_email}>")

    except Exception as e:
        logger.warning(f"Enrichment failed for '{company_name}': {e}")
