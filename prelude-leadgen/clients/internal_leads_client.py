"""
Internal Leads Database HTTP Client

Provides async HTTP client for syncing leads, companies, and contacts to the
centralized prelude_lead_db via the prelude-internal-leads-db service.

This replaces the direct database sync in data/internal_leads_sync.py.
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Service URL (configurable via environment)
INTERNAL_LEADS_SERVICE_URL = os.getenv(
    "INTERNAL_LEADS_SERVICE_URL", "http://localhost:8007"
)
API_PREFIX = "/api/internal-leads"


async def sync_lead_to_internal_db(
    lead_data: Dict[str, Any],
    personnel_data: Optional[List[Dict[str, Any]]],
    user_email: str,
    user_tenant_db: str,
    auth_token: str
) -> bool:
    """
    Send lead data to internal leads DB service via HTTP.
    Non-blocking - errors are logged but don't fail the caller.

    Args:
        lead_data: Lead/company information
        personnel_data: Optional list of contacts/personnel
        user_email: User who generated the lead
        user_tenant_db: Tenant database name
        auth_token: JWT token for authentication

    Returns:
        True if sync succeeded, False otherwise
    """
    try:
        # Map lead_data to CompanyCreateRequest format
        company_payload = {
            "company_name": lead_data.get("company", "Unknown"),
            "domain": _extract_domain(lead_data.get("website")),
            "website": lead_data.get("website"),
            "phone": lead_data.get("phone"),
            "industry": lead_data.get("industry"),
            "employee_range": lead_data.get("company_size"),
            "location_raw": lead_data.get("location"),
            "data_source": _map_source(lead_data.get("source", "manual")),
        }

        # Map ALL personnel_data to ContactCreateRequest format (not just the first)
        contacts_payload = []
        if personnel_data and len(personnel_data) > 0:
            data_source = _map_source(lead_data.get("source", "manual"))
            for idx, person in enumerate(personnel_data):
                contact = {
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "full_name": person.get("full_name") or _build_full_name(person),
                    "email": person.get("email"),
                    "phone": person.get("phone"),
                    "linkedin_url": person.get("linkedin_url"),
                    "title": person.get("position") or person.get("title"),
                    "department": person.get("department"),
                    "seniority": person.get("seniority_level"),
                    "is_decision_maker": person.get("is_decision_maker", False),
                    "is_primary": idx == 0,  # First contact is primary
                    "data_source": data_source,
                }
                contacts_payload.append(contact)

        request_body = {
            "company": company_payload,
            "contact": contacts_payload[0] if contacts_payload else None,  # Primary contact for backward compatibility
            "contacts": contacts_payload,  # All contacts
            "tenant_db_name": user_tenant_db,
            "user_email": user_email,
            "source_lead_id": lead_data.get("lead_id"),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{INTERNAL_LEADS_SERVICE_URL}{API_PREFIX}/sync/lead",
                json=request_body,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code == 200:
                result = response.json()
                contacts_count = len(contacts_payload)
                logger.info(
                    f"✅ Lead synced to internal DB: {lead_data.get('company')} "
                    f"(company_id={result.get('company', {}).get('id')}, "
                    f"new={result.get('company', {}).get('is_new')}, "
                    f"contacts={contacts_count})"
                )
                return True
            else:
                logger.warning(
                    f"Internal DB sync failed: {response.status_code} - {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.warning(f"Internal DB sync timeout for {lead_data.get('company')}")
        return False
    except httpx.ConnectError as e:
        logger.error(f"❌ Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}")
        logger.error("   Make sure the internal-leads-db service is running on port 8007")
        return False
    except Exception as e:
        logger.warning(f"Internal DB sync error (non-blocking): {e}")
        return False


async def sync_enrichment_to_internal_db(
    enrichment_batch: List[Dict[str, Any]],
    tenant_db_name: str,
    user_email: str,
    session_id: Optional[str],
    auth_token: str
) -> bool:
    """
    Batch sync enrichment results to internal DB.
    Non-blocking - errors are logged but don't fail the caller.

    Args:
        enrichment_batch: List of enrichment records
        tenant_db_name: Tenant database name
        user_email: User who ran the enrichment
        session_id: Enrichment session/workflow ID
        auth_token: JWT token for authentication

    Returns:
        True if sync succeeded, False otherwise
    """
    logger.info(f"🔄 sync_enrichment_to_internal_db called with {len(enrichment_batch)} records")
    logger.info(f"   Target URL: {INTERNAL_LEADS_SERVICE_URL}{API_PREFIX}/sync/enrichment")
    logger.info(f"   User: {user_email}, Session: {session_id}")

    try:
        companies = []
        contacts = []

        for record in enrichment_batch:
            # Only sync successful enrichments
            if record.get("enrichment_status") != "success":
                continue

            # Build company payload
            company = {
                "company_name": record.get("company_name", "Unknown"),
                "domain": _extract_domain(record.get("website")),
                "apollo_company_id": record.get("apollo_company_id"),
                "website": record.get("website"),
                "industry": record.get("industry"),
                "employee_range": record.get("company_size"),
                "location_raw": record.get("location"),
                "data_source": "enrichment",
            }
            company_idx = len(companies)  # Track index before appending
            companies.append(company)

            # Build contact payload if contact info exists
            if record.get("contact_email") or record.get("contact_name"):
                contact = {
                    "full_name": record.get("contact_name"),
                    "email": record.get("contact_email"),
                    "phone": record.get("contact_phone"),
                    "title": record.get("contact_title"),
                    "data_source": "enrichment",
                    "company_index": company_idx,  # Link to company by index
                }
                contacts.append(contact)

        if not companies:
            logger.debug("No successful enrichments to sync")
            return True

        request_body = {
            "companies": companies,
            "contacts": contacts,
            "tenant_db_name": tenant_db_name,
            "user_email": user_email,
            "session_id": session_id,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{INTERNAL_LEADS_SERVICE_URL}{API_PREFIX}/sync/enrichment",
                json=request_body,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"✅ Enrichment batch synced to internal DB: "
                    f"{result.get('companies_created', 0)} companies created, "
                    f"{result.get('companies_updated', 0)} updated, "
                    f"{result.get('contacts_created', 0)} contacts created"
                )
                return True
            else:
                logger.warning(
                    f"Enrichment sync failed: {response.status_code} - {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.warning("Enrichment sync timeout")
        return False
    except httpx.ConnectError as e:
        logger.error(f"❌ Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}")
        logger.error("   Make sure the internal-leads-db service is running on port 8007")
        return False
    except Exception as e:
        logger.warning(f"Enrichment sync error (non-blocking): {e}")
        return False


def _extract_domain(website: Optional[str]) -> Optional[str]:
    """Extract domain from website URL."""
    if not website:
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(website if "://" in website else f"https://{website}")
        domain = parsed.netloc or parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.split("/")[0] if domain else None
    except Exception:
        return None


def _build_full_name(person: Dict[str, Any]) -> Optional[str]:
    """Build full name from first/last name."""
    first = person.get("first_name", "") or ""
    last = person.get("last_name", "") or ""
    full = f"{first} {last}".strip()
    return full if full else None


def _map_source(source: str) -> str:
    """Map lead source to DataSourceType enum value."""
    source_mapping = {
        "apollo": "apollo",
        "lemlist": "lemlist",
        "google_maps": "google_maps",
        "google_search": "google_maps",
        "linkedin": "linkedin",
        "csv_import": "csv_import",
        "csv": "csv_import",
        "perplexity": "perplexity",
        "manual": "manual",
        "manual_entry": "manual",
        "enrichment": "enrichment",
    }
    return source_mapping.get(source.lower(), "manual") if source else "manual"


async def search_internal_leads(
    industry: Optional[str],
    location: Optional[str],
    max_results: int,
    auth_token: str,
    keywords: Optional[List[str]] = None,
    company_size: Optional[str] = None,
    industry_search_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search internal leads DB for matching companies before calling third-party APIs.

    Returns companies in a format compatible with ApolloPreviewLead for seamless integration.

    Args:
        industry: Industry to search for
        location: Location to search for
        max_results: Maximum number of results
        auth_token: JWT token for authentication
        keywords: Optional keywords to search
        company_size: Optional company size filter
        industry_search_terms: Lowercase partial terms for SQL ILIKE matching

    Returns:
        List of leads in ApolloPreviewLead-compatible format, or empty list on error
    """
    try:
        request_body = {
            "industry": industry,
            "industry_search_terms": industry_search_terms,
            "location": location,
            "max_results": max_results,
            "keywords": keywords,
            "company_size": company_size,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{INTERNAL_LEADS_SERVICE_URL}{API_PREFIX}/companies/search",
                json=request_body,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("companies"):
                    companies = result["companies"]
                    logger.info(
                        f"🔍 Internal leads DB search: found {len(companies)} companies "
                        f"for industry={industry}, location={location}"
                    )
                    # Map to ApolloPreviewLead-compatible format
                    return [_map_to_preview_lead(c) for c in companies]
                else:
                    logger.debug(f"Internal leads DB search returned no results")
                    return []
            else:
                logger.warning(
                    f"Internal leads DB search failed: {response.status_code} - {response.text}"
                )
                return []

    except httpx.TimeoutException:
        logger.warning("Internal leads DB search timeout - falling back to third-party APIs")
        return []
    except httpx.ConnectError as e:
        logger.debug(f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL}: {e}")
        logger.debug("Falling back to third-party APIs only")
        return []
    except Exception as e:
        logger.warning(f"Internal leads DB search error: {e}")
        return []


def _map_to_preview_lead(company: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map internal leads DB company to ApolloPreviewLead-compatible format.

    The returned dict matches the structure expected by ApolloPreviewLead schema.
    """
    return {
        # Company info
        "company_name": company.get("company_name"),
        "website": company.get("website") or company.get("domain"),
        "industry": company.get("industry"),
        "location": company.get("location"),
        "company_size": company.get("company_size"),
        "apollo_company_id": company.get("apollo_company_id"),
        # Contact info (already enriched in internal DB)
        "contact_name": company.get("contact_name"),
        "contact_email": company.get("contact_email"),
        "contact_title": company.get("contact_title"),
        "contact_phone": company.get("contact_phone"),
        "is_decision_maker": company.get("is_decision_maker", False),
        # Metadata to indicate source (no underscore prefix - Pydantic V2 compatibility)
        "lead_source": "internal_db",
        "internal_company_id": company.get("company_id"),
        "has_contact": bool(company.get("contact_email")),
    }
