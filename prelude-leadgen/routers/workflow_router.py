"""
Workflow Router for Lead Generation.
Handles two-stage preview/enrich workflow endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from service_core.db import get_tenant_connection
from apollo_io.schemas import ApolloEnrichmentRequest

# Security scheme for extracting raw token
security = HTTPBearer()
from apollo_io.service import get_apollo_service
from database.queries import save_enrichment_history, get_employee_id_by_email
from utils.redis_cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/workflow/preview")
async def preview_workflow(
    industry: str,
    location: str,
    max_results: int = 50,
    company_size: str = None,
    keywords: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    tenant=Depends(get_tenant_connection)
):
    """
    STAGE 1: Generate preview leads with automatic deduplication.

    First checks internal leads DB for matching leads, then fetches
    remaining from Apollo if needed. Returns company data after filtering
    out companies already in the user's database.

    Automatically retries up to 2 times if results < max_results.
    """
    try:
        conn, user = tenant
        user_email = user.get("email")
        auth_token = credentials.credentials if credentials else None

        # Request deduplication: check if same request is in progress
        cache = get_cache()
        lock_key = f"preview:{user_email}:{industry}:{location}:{max_results}:{company_size or 'any'}:{keywords or 'none'}"

        if not cache.acquire_lock(lock_key, timeout=30):
            logger.info(f"Duplicate preview request detected for {user_email}, waiting for result...")
            import asyncio
            await asyncio.sleep(2)
            cached_response = cache.cache_apollo_search(
                location=location,
                industry=industry,
                max_results=max_results,
                company_size=company_size,
                keywords=keywords
            )
            if cached_response:
                return cached_response
            else:
                raise HTTPException(status_code=429, detail="Request in progress, please wait")

        try:
            # Parse keywords if provided
            keywords_list = [k.strip() for k in keywords.split(",")] if keywords else None

            # Get Apollo service
            apollo_service = get_apollo_service()

            # Execute preview search with deduplication
            response = await apollo_service.preview_leads_with_dedup(
                location=location,
                industry=industry,
                max_results=max_results,
                user_email=user_email,
                auth_token=auth_token,
                company_size=company_size,
                keywords=keywords_list
            )
        finally:
            cache.release_lock(lock_key)

        # Convert Pydantic models to dicts for JSON response
        return {
            "status": response.status,
            "message": response.message,
            "leads": [lead.dict() for lead in response.leads],
            "total_found": response.total_found,
            "duration_seconds": response.duration_seconds
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/enrich")
async def enrich_workflow(
    request: ApolloEnrichmentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    tenant=Depends(get_tenant_connection)
):
    """
    STAGE 2: Enrich selected preview leads with email contacts only.

    Takes company IDs from preview results and fetches decision maker
    emails (no phone numbers to reduce cost).

    Leads from internal DB (already have contact info) are returned directly
    without calling Apollo API. Only Apollo-sourced leads need enrichment.

    Also saves enrichment history to database for tracking.
    Uses Redis lock to prevent duplicate enrichment requests (double-click protection).
    """
    try:
        conn, user = tenant
        user_email = user.get("email")

        if not user_email:
            raise HTTPException(status_code=400, detail="Email not found in token")

        # Redis deduplication lock FIRST
        import hashlib
        cache = get_cache()
        company_ids_hash = hashlib.md5(str(sorted(request.company_ids)).encode()).hexdigest()[:12]
        lock_key = f"enrich:{user_email}:{company_ids_hash}"

        if not cache.acquire_lock(lock_key, timeout=120):
            logger.warning(f"Duplicate enrichment request from {user_email}")
            raise HTTPException(
                status_code=429,
                detail="Enrichment already in progress for these companies. Please wait."
            )

        logger.info(f"Redis LOCK ACQUIRED: {lock_key}")

        try:
            # Lookup employee_id
            employee_id = await get_employee_id_by_email(conn, user_email)

            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found for this email")

            # Separate internal DB leads from Apollo leads
            internal_db_leads = []
            apollo_company_ids = []
            apollo_companies = []

            if request.companies:
                for company in request.companies:
                    source = company.get('lead_source', 'apollo')
                    if source == 'internal_db' and company.get('contact_email'):
                        internal_db_leads.append(company)
                        logger.info(f"Internal DB lead (skip enrichment): {company.get('company_name')} - {company.get('contact_email')}")
                    else:
                        apollo_company_id = company.get('apollo_company_id')
                        if apollo_company_id:
                            apollo_company_ids.append(apollo_company_id)
                            apollo_companies.append(company)

            logger.info(f"Enrichment split: {len(internal_db_leads)} from internal DB, {len(apollo_company_ids)} need Apollo enrichment")

            # Get Apollo service
            apollo_service = get_apollo_service()

            # Only call Apollo for leads that need enrichment
            if apollo_company_ids:
                response = await apollo_service.enrich_selected_emails(
                    company_ids=apollo_company_ids,
                    job_titles=request.job_titles,
                    department=request.department,
                    seniority_level=request.seniority_level,
                    companies=apollo_companies
                )
            else:
                from apollo_io.schemas import ApolloEnrichmentResponse
                response = ApolloEnrichmentResponse(
                    status="completed",
                    total_enriched=0,
                    failed_count=0
                )

            # Save enrichment history for each enriched lead
            import uuid
            session_id = str(uuid.uuid4())

            # Track which companies were successfully enriched
            enriched_company_ids = {lead.apollo_company_id for lead in response.leads}
            logger.info(f"Enriched company IDs: {enriched_company_ids}")

            from database.queries import normalize_company_name
            enriched_company_names = {normalize_company_name(lead.company_name) for lead in response.leads}
            logger.info(f"Enriched company names: {enriched_company_names}")

            # OPTIMIZED: Batch insert enrichments
            from database.queries_optimized import save_enrichment_history_batch

            enrichment_batch = []

            for lead in response.leads:
                has_valid_email = (
                    lead.contact_email is not None and
                    lead.contact_email.strip() != '' and
                    'not_unlocked' not in lead.contact_email.lower() and
                    not lead.contact_email.endswith('@domain.com')
                )

                if has_valid_email:
                    logger.info(f"Preparing successful enrichment for: {lead.company_name} (ID: {lead.apollo_company_id}) - Email: {lead.contact_email}")
                    enrichment_status = 'success'
                    enrichment_cost = 1
                else:
                    logger.info(f"Preparing failed enrichment for: {lead.company_name} (ID: {lead.apollo_company_id}) - No valid email (got: {lead.contact_email})")
                    enrichment_status = 'failed'
                    enrichment_cost = 0

                enrichment_data = {
                    'session_id': session_id,
                    'company_name': lead.company_name,
                    'apollo_company_id': lead.apollo_company_id,
                    'website': lead.website,
                    'location': lead.location,
                    'industry': lead.industry,
                    'company_size': None,
                    'contact_name': lead.contact_name,
                    'contact_title': lead.contact_title,
                    'contact_email': lead.contact_email,
                    'contact_phone': None,
                    'enrichment_source': 'apollo',
                    'enrichment_status': enrichment_status,
                    'enrichment_cost_credits': enrichment_cost,
                    'final_score': lead.final_score,
                    'search_intent_industry': None,
                    'search_intent_location': None,
                    'search_intent_keywords': None,
                    'workflow_id': session_id
                }
                enrichment_batch.append(enrichment_data)

            # Batch insert all enrichments at once
            if enrichment_batch:
                await save_enrichment_history_batch(conn, enrichment_batch, employee_id)
                logger.info(f"Batch saved {len(enrichment_batch)} enrichment records")

                # Sync to internal leads DB (fire-and-forget via HTTP)
                try:
                    import asyncio
                    from clients.internal_leads_client import sync_enrichment_to_internal_db

                    auth_token = credentials.credentials if credentials else ''

                    logger.info(f"Starting internal DB sync for {len(enrichment_batch)} enrichments (session: {session_id})")

                    def _sync_done_callback(task):
                        try:
                            exc = task.exception()
                            if exc:
                                logger.error(f"Internal DB sync task failed: {exc}")
                        except asyncio.CancelledError:
                            logger.warning("Internal DB sync task was cancelled")

                    sync_task = asyncio.create_task(sync_enrichment_to_internal_db(
                        enrichment_batch=enrichment_batch,
                        tenant_db_name='unknown',
                        user_email=user_email,
                        session_id=session_id,
                        auth_token=auth_token
                    ))
                    sync_task.add_done_callback(_sync_done_callback)
                except Exception as sync_error:
                    logger.warning(f"Internal enrichment sync failed (non-critical): {sync_error}")

            # Invalidate enrichment history cache after successful enrichment
            cache.delete(f"enrichment_history:{employee_id}")
            logger.info(f"Redis CACHE INVALIDATED: enrichment_history:{employee_id}")

            # Save failed enrichments
            internal_db_names = {normalize_company_name(c.get('company_name', '')) for c in internal_db_leads}

            if request.companies:
                for company in request.companies:
                    company_name = company.get('company_name', 'Unknown')
                    normalized_name = normalize_company_name(company_name)

                    if normalized_name in internal_db_names:
                        continue

                    if normalized_name in enriched_company_names:
                        logger.info(f"SKIPPED: Already enriched - {company_name}")
                        continue

                    logger.info(f"Saving failed enrichment: No Apollo match for {company_name}")
                    enrichment_data = {
                        'session_id': session_id,
                        'company_name': company_name,
                        'apollo_company_id': company.get('apollo_company_id'),
                        'website': company.get('website'),
                        'location': company.get('location'),
                        'industry': company.get('industry'),
                        'company_size': None,
                        'contact_name': None,
                        'contact_title': None,
                        'contact_email': None,
                        'contact_phone': None,
                        'enrichment_source': company.get('source', 'unknown'),
                        'enrichment_status': 'failed',
                        'enrichment_cost_credits': 0,
                        'final_score': None,
                        'search_intent_industry': None,
                        'search_intent_location': None,
                        'search_intent_keywords': None,
                        'workflow_id': session_id
                    }

                    await save_enrichment_history(conn, enrichment_data, employee_id)

            # Combine Apollo-enriched leads with internal DB leads
            all_enriched_leads = []

            for lead in response.leads:
                all_enriched_leads.append(lead.dict())

            for company in internal_db_leads:
                internal_lead = {
                    "company_name": company.get("company_name"),
                    "website": company.get("website"),
                    "industry": company.get("industry"),
                    "location": company.get("location"),
                    "apollo_company_id": company.get("apollo_company_id"),
                    "contact_name": company.get("contact_name"),
                    "contact_email": company.get("contact_email"),
                    "contact_title": company.get("contact_title"),
                    "contact_phone": company.get("contact_phone"),
                    "is_enriched": True,
                    "lead_source": "internal_db",
                    "internal_company_id": company.get("internal_company_id"),
                }
                all_enriched_leads.append(internal_lead)

                enrichment_data = {
                    'session_id': session_id,
                    'company_name': company.get("company_name"),
                    'apollo_company_id': company.get("apollo_company_id"),
                    'website': company.get("website"),
                    'location': company.get("location"),
                    'industry': company.get("industry"),
                    'company_size': company.get("company_size"),
                    'contact_name': company.get("contact_name"),
                    'contact_title': company.get("contact_title"),
                    'contact_email': company.get("contact_email"),
                    'contact_phone': company.get("contact_phone"),
                    'enrichment_source': 'internal_db',
                    'enrichment_status': 'success',
                    'enrichment_cost_credits': 0,
                    'final_score': None,
                    'search_intent_industry': None,
                    'search_intent_location': None,
                    'search_intent_keywords': None,
                    'workflow_id': session_id
                }
                await save_enrichment_history(conn, enrichment_data, employee_id)

            total_enriched = response.total_enriched + len(internal_db_leads)
            logger.info(f"Total enriched leads: {total_enriched} (Apollo: {response.total_enriched}, Internal DB: {len(internal_db_leads)})")

            return {
                "status": response.status,
                "message": response.message,
                "leads": all_enriched_leads,
                "total_enriched": total_enriched,
                "failed_count": response.failed_count,
                "duration_seconds": response.duration_seconds,
                "internal_db_count": len(internal_db_leads),
                "apollo_count": response.total_enriched,
            }
        finally:
            cache.release_lock(lock_key)
            logger.info(f"Redis LOCK RELEASED: {lock_key}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrichment workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
