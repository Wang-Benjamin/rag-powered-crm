"""Lemlist lead service — drop-in replacement for ApolloLeadService.

Exposes the same method signatures and return types so that
existing workflow services need zero changes.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .client import LemlistClient, LemlistConfig

from utils.redis_cache import get_cache
from utils.circuit_breaker import get_circuit_breaker, CircuitBreakerError

logger = logging.getLogger(__name__)

lemlist_breaker = get_circuit_breaker("lemlist_api", fail_max=5, timeout_duration=60)


class LemlistLeadService:
    """Drop-in replacement for ``ApolloLeadService``."""

    def __init__(self, config: Optional[LemlistConfig] = None):
        if config is None:
            api_key = os.getenv("LEMLIST_API_KEY")
            if not api_key:
                raise ValueError("LEMLIST_API_KEY environment variable is required")
            config = LemlistConfig(
                api_key=api_key,
                base_url=os.getenv("LEMLIST_BASE_URL", "https://api.lemlist.com/api"),
                timeout_seconds=int(os.getenv("LEMLIST_TIMEOUT", "30")),
            )
        self.config = config

    # ------------------------------------------------------------------
    # STAGE 1: Preview
    # ------------------------------------------------------------------

    async def preview_leads_with_dedup(
        self,
        location: str,
        industry: str,
        max_results: int = 50,
        user_email: str = None,
        auth_token: str = None,
        **filters,
    ):
        """STAGE 1 — identical signature and return type to ApolloLeadService."""
        from apollo_io.schemas import ApolloPreviewResponse, ApolloPreviewLead
        from database.queries import (
            get_existing_company_names,
            get_enriched_company_names_for_user,
            normalize_company_name,
        )
        from clients.internal_leads_client import search_internal_leads

        start_time = datetime.now(timezone.utc)

        # Check cache (reuse the existing apollo cache infra — same key scheme)
        cache = get_cache()
        cached = cache.cache_apollo_search(
            location=location, industry=industry, max_results=max_results, **filters,
        )
        if cached:
            logger.info(f"Returning cached preview for {industry} in {location}")
            return ApolloPreviewResponse(**cached)

        try:
            response = ApolloPreviewResponse(status="in_progress", started_at=start_time)

            # Dedup sets
            existing_names: set = set()
            if user_email:
                try:
                    existing_names = get_existing_company_names(user_email)
                    enriched_names = get_enriched_company_names_for_user(user_email)
                    existing_names = existing_names.union(enriched_names)
                    logger.info(f"Dedup: {len(existing_names)} existing companies")
                except Exception as e:
                    logger.warning(f"Dedup query failed: {e}")

            all_leads: List[ApolloPreviewLead] = []
            internal_db_count = 0
            lemlist_count = 0

            # ---- Step 1: internal leads DB ----
            if auth_token:
                try:
                    internal_results = await search_internal_leads(
                        industry=industry,
                        location=location,
                        max_results=max_results,
                        auth_token=auth_token,
                        keywords=filters.get("keywords"),
                        company_size=filters.get("company_size"),
                    )
                    if internal_results:
                        for cd in internal_results:
                            name = cd.get("company_name", "")
                            if normalize_company_name(name) in existing_names:
                                continue
                            try:
                                cd["lead_source"] = "internal_db"
                                all_leads.append(ApolloPreviewLead(**cd))
                                internal_db_count += 1
                                if len(all_leads) >= max_results:
                                    break
                            except Exception:
                                continue
                    logger.info(f"Internal DB: {internal_db_count} leads")
                except Exception as e:
                    logger.warning(f"Internal DB search failed: {e}")

            # ---- Step 2: Lemlist company search if shortfall ----
            shortfall = max_results - len(all_leads)
            if shortfall > 0:
                logger.info(f"Need {shortfall} more from Lemlist")
                internal_db_names = {
                    normalize_company_name(l.company_name) for l in all_leads
                }
                page = 1
                max_pages = 4
                dupes = 0

                async with LemlistClient(self.config) as client:
                    while len(all_leads) < max_results and page <= max_pages:
                        needed = max_results - len(all_leads)
                        fetch_size = min(500, max(15, int(needed * 2.5)))

                        try:
                            async def _fetch():
                                return await client.search_companies_preview(
                                    industry=industry,
                                    location=location,
                                    max_results=fetch_size,
                                    company_size=filters.get("company_size"),
                                    keywords=filters.get("keywords"),
                                    page=page,
                                )

                            raw = await lemlist_breaker.call_async(_fetch)
                        except CircuitBreakerError as e:
                            logger.error(f"Lemlist circuit breaker open: {e}")
                            break

                        if not raw:
                            break

                        before = len(all_leads)
                        for company in raw:
                            cname = company.get("company_name", "")
                            norm = normalize_company_name(cname)
                            if norm in existing_names or norm in internal_db_names:
                                dupes += 1
                                continue
                            current = {normalize_company_name(l.company_name) for l in all_leads}
                            if norm in current:
                                dupes += 1
                                continue
                            try:
                                company["lead_source"] = "lemlist"
                                all_leads.append(ApolloPreviewLead(**company))
                                lemlist_count += 1
                                if len(all_leads) >= max_results:
                                    break
                            except Exception:
                                continue

                        added = len(all_leads) - before
                        logger.info(f"Page {page}: +{added}, {len(all_leads)}/{max_results}, {dupes} dupes")
                        if len(all_leads) >= max_results:
                            break
                        page += 1

            final = all_leads[:max_results]
            response.status = "completed"
            response.leads = final
            response.total_found = len(final)
            response.completed_at = datetime.now(timezone.utc)
            response.duration_seconds = (response.completed_at - response.started_at).total_seconds()

            cache.store_apollo_search(
                location=location, industry=industry,
                max_results=max_results, results=response.dict(), **filters,
            )
            logger.info(
                f"Preview done: {len(final)} leads "
                f"(internal_db: {internal_db_count}, lemlist: {lemlist_count})"
            )
            return response

        except Exception as e:
            logger.error(f"Preview failed: {e}")
            resp = ApolloPreviewResponse(
                status="failed", message=str(e),
                started_at=start_time, completed_at=datetime.now(timezone.utc),
            )
            resp.errors.append(str(e))
            return resp

    # ------------------------------------------------------------------
    # STAGE 2: Enrich
    # ------------------------------------------------------------------

    async def enrich_selected_emails(
        self,
        company_ids: List[str],
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None,
        companies: Optional[List[Dict[str, Any]]] = None,
    ):
        """STAGE 2 — identical signature and return type to ApolloLeadService."""
        from apollo_io.schemas import ApolloEnrichmentResponse, ApolloEnrichedLead

        start_time = datetime.now(timezone.utc)

        try:
            response = ApolloEnrichmentResponse(status="in_progress", started_at=start_time)
            enriched_leads = []
            failed_count = 0

            async with LemlistClient(self.config) as client:
                enriched_data = await client.enrich_company_emails(
                    company_ids=company_ids,
                    companies=companies,
                    job_titles=job_titles,
                    department=department,
                    seniority_level=seniority_level,
                )
                for data in enriched_data:
                    try:
                        enriched_leads.append(ApolloEnrichedLead(**data))
                    except Exception as e:
                        logger.error(f"Error creating enriched lead: {e}")
                        failed_count += 1

            response.status = "completed"
            response.leads = enriched_leads
            response.total_enriched = len(enriched_leads)
            response.failed_count = failed_count
            response.completed_at = datetime.now(timezone.utc)
            response.duration_seconds = (response.completed_at - response.started_at).total_seconds()
            logger.info(f"Enrich done: {len(enriched_leads)} ok, {failed_count} failed / {len(company_ids)} requested")
            return response

        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            resp = ApolloEnrichmentResponse(
                status="failed", message=str(e),
                started_at=start_time, completed_at=datetime.now(timezone.utc),
            )
            resp.errors.append(str(e))
            return resp

    # ------------------------------------------------------------------
    # Full search + enrich compatibility path
    # ------------------------------------------------------------------

    async def search_leads(self, request):
        """Full search + enrich — same signature as ApolloLeadService.search_leads()."""
        from apollo_io.schemas import ApolloSearchResponse, ApolloLead

        start_time = datetime.now(timezone.utc)
        try:
            async with LemlistClient(self.config) as client:
                raw = await client.search_companies_preview(
                    industry=request.industry,
                    location=request.location,
                    max_results=request.max_results,
                    company_size=request.company_size,
                    keywords=request.keywords,
                )
                enriched = await client.enrich_company_emails(
                    company_ids=[c["apollo_company_id"] for c in raw],
                    companies=[
                        {"company_name": c["company_name"], "website": c.get("website", ""), "location": c.get("location", "")}
                        for c in raw
                    ],
                    job_titles=request.job_titles,
                    department=request.department,
                    seniority_level=request.seniority_level,
                )

            leads = []
            for d in enriched:
                try:
                    leads.append(ApolloLead(
                        company_name=d.get("company_name", ""),
                        contact_name=d.get("contact_name"),
                        contact_email=d.get("contact_email"),
                        website=d.get("website"),
                        industry=d.get("industry"),
                        location=d.get("location"),
                        title=d.get("contact_title"),
                        final_score=d.get("final_score", 50),
                        source="lemlist",
                        apollo_person_id=d.get("apollo_person_id"),
                        apollo_company_id=d.get("apollo_company_id"),
                    ))
                except Exception:
                    continue

            return ApolloSearchResponse(
                status="completed",
                leads=leads,
                total_found=len(leads),
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"search_leads failed: {e}")
            return ApolloSearchResponse(
                status="failed", message=str(e),
                started_at=start_time, completed_at=datetime.now(timezone.utc),
            )
