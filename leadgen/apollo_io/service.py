"""
Apollo.io lead generation service focused on essential business data.

High-quality lead generation optimized for the four most important fields:
- Company name
- Contact name
- Contact email
- Website URL
"""

import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .client import ApolloClient
from .schemas import (
    ApolloSearchRequest,
    ApolloSearchResponse,
    ApolloLead,
    ApolloConfig,
    ApolloApiError,
)

# Import optimization utilities
from utils.redis_cache import get_cache
from utils.circuit_breaker import apollo_breaker, CircuitBreakerError
from utils.rate_limiter import apollo_rate_limiter

logger = logging.getLogger(__name__)


class ApolloLeadService:
    """
    Apollo.io lead generation service optimized for essential lead data.
    
    Designed as a drop-in replacement for Yellow Pages scraper with
    focus on high-quality contact information.
    """
    
    def __init__(self, config: Optional[ApolloConfig] = None):
        """Initialize Apollo service with configuration."""
        if config is None:
            # Load from environment variables
            api_key = os.getenv("APOLLO_API_KEY")
            if not api_key:
                raise ValueError("APOLLO_API_KEY environment variable is required")
            
            config = ApolloConfig(
                api_key=api_key,
                base_url=os.getenv("APOLLO_BASE_URL", "https://api.apollo.io"),
                requests_per_minute=int(os.getenv("APOLLO_RATE_LIMIT", "60")),
                timeout_seconds=int(os.getenv("APOLLO_TIMEOUT", "30")),
                require_email=os.getenv("APOLLO_REQUIRE_EMAIL", "true").lower() == "true",
                require_website=os.getenv("APOLLO_REQUIRE_WEBSITE", "false").lower() == "true",
                min_lead_score=int(os.getenv("APOLLO_MIN_SCORE", "30")),
                fetch_multiplier=float(os.getenv("APOLLO_FETCH_MULTIPLIER", "1.5")),
                max_retry_attempts=int(os.getenv("APOLLO_MAX_RETRIES", "1")),
                estimated_filter_rate=float(os.getenv("APOLLO_FILTER_RATE", "0.7"))
            )
        
        self.config = config
        self._client: Optional[ApolloClient] = None
    
    async def search_leads(self, request: ApolloSearchRequest) -> ApolloSearchResponse:
        """
        Execute Apollo.io lead search with smart pagination to meet target results.

        Uses fetch_multiplier and retry logic to compensate for quality filtering.
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Initialize response
            response = ApolloSearchResponse(
                status="in_progress",
                started_at=start_time
            )

            # Create Apollo client
            async with ApolloClient(self.config) as client:
                all_processed_leads = []
                total_raw_fetched = 0
                attempt = 1

                # Calculate initial fetch size using multiplier
                initial_target = max(int(request.max_results * self.config.fetch_multiplier), request.max_results + 2)
                logger.info(f"Smart pagination: targeting {request.max_results} leads, initial fetch {initial_target} raw leads")

                # First attempt with multiplied target and all filters
                raw_leads = await client.search_people_and_companies(
                    industry=request.industry,
                    location=request.location,
                    max_results=initial_target,
                    company_size=request.company_size,
                    keywords=request.keywords,
                    job_titles=request.job_titles,
                    department=request.department,
                    seniority_level=request.seniority_level
                )

                total_raw_fetched += len(raw_leads)
                processed_leads = await self._process_leads(raw_leads, request)
                all_processed_leads.extend(processed_leads)

                logger.info(f"Attempt {attempt}: fetched {len(raw_leads)} raw → {len(processed_leads)} filtered → {len(all_processed_leads)} total")

                # Retry logic if we don't have enough leads
                while len(all_processed_leads) < request.max_results and attempt < self.config.max_retry_attempts + 1:
                    attempt += 1
                    shortage = request.max_results - len(all_processed_leads)

                    # Calculate how many more raw leads we need based on current filter rate
                    current_filter_rate = len(all_processed_leads) / total_raw_fetched if total_raw_fetched > 0 else self.config.estimated_filter_rate
                    additional_raw_needed = max(int(shortage / current_filter_rate), shortage + 3)

                    logger.info(f"Attempt {attempt}: need {shortage} more leads, requesting {additional_raw_needed} additional raw (filter rate: {current_filter_rate:.2f})")

                    # Fetch additional leads - Apollo will handle pagination internally
                    additional_raw = await client.search_people_and_companies(
                        industry=request.industry,
                        location=request.location,
                        max_results=additional_raw_needed,
                        company_size=request.company_size,
                        keywords=request.keywords
                    )

                    if not additional_raw:
                        logger.warning(f"Attempt {attempt}: Apollo returned no additional results, ending retry")
                        break

                    total_raw_fetched += len(additional_raw)
                    additional_processed = await self._process_leads(additional_raw, request)

                    # Remove duplicates based on company name + contact email
                    new_leads = []
                    existing_keys = {(lead.company_name, lead.contact_email or '') for lead in all_processed_leads}

                    for lead in additional_processed:
                        lead_key = (lead.company_name, lead.contact_email or '')
                        if lead_key not in existing_keys:
                            new_leads.append(lead)
                            existing_keys.add(lead_key)

                    all_processed_leads.extend(new_leads)
                    logger.info(f"Attempt {attempt}: fetched {len(additional_raw)} raw → {len(additional_processed)} filtered → {len(new_leads)} new → {len(all_processed_leads)} total")

                # Limit to requested amount and sort by score
                final_leads = sorted(all_processed_leads, key=lambda x: x.final_score, reverse=True)[:request.max_results]

                # Calculate quality metrics
                metrics = self._calculate_quality_metrics(final_leads)

                # Finalize response
                response.status = "completed"
                response.leads = final_leads
                response.total_found = len(final_leads)
                response.completed_at = datetime.now(timezone.utc)
                response.duration_seconds = (response.completed_at - response.started_at).total_seconds()

                # Update quality metrics
                response.leads_with_email = metrics["leads_with_email"]
                response.leads_with_website = metrics["leads_with_website"]
                response.leads_with_contact_name = metrics["leads_with_contact_name"]
                response.leads_with_complete_data = metrics["leads_with_complete_data"]

                success_rate = (len(final_leads) / request.max_results * 100) if request.max_results > 0 else 100
                logger.info(f"Apollo smart search completed: {len(final_leads)}/{request.max_results} leads ({success_rate:.1f}%) from {total_raw_fetched} raw in {response.duration_seconds:.1f}s")
                return response

        except ApolloApiError as e:
            logger.error(f"Apollo API error: {e}")
            response.status = "failed"
            response.message = str(e)
            response.errors.append(str(e))
            response.completed_at = datetime.now(timezone.utc)
            return response

        except Exception as e:
            logger.error(f"Unexpected Apollo error: {e}")
            response.status = "failed"
            response.message = f"Unexpected error: {str(e)}"
            response.errors.append(str(e))
            response.completed_at = datetime.now(timezone.utc)
            return response
    
    async def _process_leads(
        self, 
        raw_leads: List[dict], 
        request: ApolloSearchRequest
    ) -> List[ApolloLead]:
        """
        Process raw Apollo leads into structured ApolloLead objects.
        
        Applies quality filters and scoring based on essential fields.
        """
        processed_leads = []
        
        for raw_lead in raw_leads:
            try:
                logger.debug(f"Processing raw lead: {raw_lead}")
                # Create Apollo lead object
                apollo_lead = ApolloLead(
                    company_name=raw_lead.get("company_name", ""),
                    contact_name=raw_lead.get("contact_name"),
                    contact_email=raw_lead.get("contact_email"),
                    website=raw_lead.get("website"),
                    industry=raw_lead.get("industry") or request.industry,
                    location=raw_lead.get("location") or request.location,
                    title=raw_lead.get("title"),
                    final_score=raw_lead.get("final_score", 50),
                    apollo_person_id=raw_lead.get("apollo_person_id"),
                    apollo_company_id=raw_lead.get("apollo_company_id"),
                    scraped_at=datetime.now(timezone.utc)
                )
                logger.debug(f"Created ApolloLead with contact_name: {apollo_lead.contact_name}")
                
                # Apply quality filters
                if self._meets_quality_requirements(apollo_lead):
                    processed_leads.append(apollo_lead)
                    
            except Exception as e:
                logger.debug(f"Failed to process lead {raw_lead.get('company_name', 'Unknown')}: {e}")
                continue
        
        # Sort by lead score (highest quality first)
        processed_leads.sort(key=lambda x: x.final_score, reverse=True)
        
        # Limit to max_results
        return processed_leads[:request.max_results]
    
    def _meets_quality_requirements(self, lead: ApolloLead) -> bool:
        """
        Check if lead meets minimum quality requirements based on essential fields.
        """
        # Must have company name (essential)
        if not lead.company_name or len(lead.company_name.strip()) < 2:
            return False
        
        # Apply email requirement if configured
        if self.config.require_email and not lead.contact_email:
            return False
        
        # Apply website requirement if configured  
        if self.config.require_website and not lead.website:
            return False
        
        # Apply minimum score requirement
        if lead.final_score < self.config.min_lead_score:
            return False
        
        # Must have at least one contact method (email or website)
        if not lead.contact_email and not lead.website:
            return False
        
        return True
    
    def _calculate_quality_metrics(self, leads: List[ApolloLead]) -> dict:
        """Calculate quality metrics for the essential lead fields."""
        metrics = {
            "leads_with_email": 0,
            "leads_with_website": 0, 
            "leads_with_contact_name": 0,
            "leads_with_complete_data": 0
        }
        
        for lead in leads:
            if lead.contact_email:
                metrics["leads_with_email"] += 1
            
            if lead.website:
                metrics["leads_with_website"] += 1
                
            if lead.contact_name:
                metrics["leads_with_contact_name"] += 1
            
            # Complete data = all four essential fields
            if (lead.company_name and lead.contact_name and 
                lead.contact_email and lead.website):
                metrics["leads_with_complete_data"] += 1
        
        return metrics
    
    # ===== TWO-STAGE WORKFLOW METHODS =====

    async def preview_leads_with_dedup(
        self,
        location: str,
        industry: str,
        max_results: int = 50,
        user_email: str = None,
        auth_token: str = None,
        **filters
    ):
        """
        STAGE 1: Generate preview leads with automatic deduplication.

        Workflow:
        1. Check Redis cache for previous results
        2. Search internal leads DB first (already enriched leads)
        3. If not enough, fetch remaining from Apollo (with circuit breaker protection)
        4. Query database for existing company names (by user)
        5. Filter out duplicates silently
        6. If results < max_results, retry with pagination (max 2 retries)
        7. Cache and return unique preview leads

        Args:
            location: Geographic location
            industry: Industry category
            max_results: Target number of NEW companies
            user_email: User identifier for database filtering
            auth_token: JWT token for internal leads DB authentication
            **filters: Additional filters (company_size, keywords, etc.)

        Returns:
            ApolloPreviewResponse with unique preview leads
        """
        from .schemas import ApolloPreviewResponse, ApolloPreviewLead
        from database.queries import get_existing_company_names, get_enriched_company_names_for_user, normalize_company_name
        from clients.internal_leads_client import search_internal_leads

        start_time = datetime.now(timezone.utc)

        # Check cache first
        cache = get_cache()
        cached_response = cache.cache_apollo_search(
            location=location,
            industry=industry,
            max_results=max_results,
            **filters
        )
        if cached_response:
            logger.info(f"Returning cached preview results for {industry} in {location}")
            return ApolloPreviewResponse(**cached_response)

        try:
            # Initialize response
            response = ApolloPreviewResponse(
                status="in_progress",
                started_at=start_time
            )

            # Get existing company names from database (for deduplication)
            existing_names = set()
            enriched_names = set()

            if user_email:
                try:
                    # Get companies from leads database (all users)
                    existing_names = get_existing_company_names(user_email)
                    logger.info(f"Found {len(existing_names)} existing companies in leads database")

                    # Get companies from enrichment history (current user only)
                    enriched_names = get_enriched_company_names_for_user(user_email)
                    logger.info(f"Found {len(enriched_names)} enriched companies for current user")

                    # Combine both sets for comprehensive deduplication
                    all_existing_names = existing_names.union(enriched_names)
                    logger.info(f"Total companies to exclude: {len(all_existing_names)} (leads: {len(existing_names)}, enriched: {len(enriched_names)})")
                    existing_names = all_existing_names

                except Exception as e:
                    logger.warning(f"Could not fetch existing companies: {e}")
                    # Continue without deduplication if database query fails

            all_preview_leads = []
            internal_db_count = 0
            apollo_count = 0

            # ===== STEP 1: Search internal leads DB first =====
            if auth_token:
                try:
                    internal_results = await search_internal_leads(
                        industry=industry,
                        location=location,
                        max_results=max_results,
                        auth_token=auth_token,
                        keywords=filters.get('keywords'),
                        company_size=filters.get('company_size'),
                    )

                    if internal_results:
                        for company_data in internal_results:
                            company_name = company_data.get('company_name', '')
                            normalized_name = normalize_company_name(company_name)

                            # Skip if already in user's existing leads
                            if normalized_name in existing_names:
                                logger.debug(f"Skipping internal DB lead (already in user's leads): {company_name}")
                                continue

                            # Create preview lead from internal DB data
                            try:
                                # Add source marker to track origin
                                company_data['lead_source'] = 'internal_db'
                                preview_lead = ApolloPreviewLead(**company_data)
                                all_preview_leads.append(preview_lead)
                                internal_db_count += 1

                                if len(all_preview_leads) >= max_results:
                                    break
                            except Exception as e:
                                logger.debug(f"Error creating preview lead from internal DB: {e}")
                                continue

                        logger.info(f"📦 Internal leads DB: Found {internal_db_count} matching leads")

                except Exception as e:
                    logger.warning(f"Internal leads DB search failed, falling back to Apollo: {e}")

            # ===== STEP 2: If not enough, fetch remaining from Apollo =====
            shortfall = max_results - len(all_preview_leads)
            if shortfall > 0:
                logger.info(f"Need {shortfall} more leads from Apollo (have {len(all_preview_leads)} from internal DB)")

                page = 1
                max_pages = 4  # Maximum number of pages to try (initial + 3 retries)
                duplicates_filtered = 0

                # Track internal DB company names for Apollo deduplication
                internal_db_names = {normalize_company_name(l.company_name) for l in all_preview_leads}

                # Create Apollo client
                async with ApolloClient(self.config) as client:
                    while len(all_preview_leads) < max_results and page <= max_pages:
                        # Calculate how many more unique leads we need
                        needed = max_results - len(all_preview_leads)

                        # Calculate fetch size with aggressive buffer for duplicates
                        # Use higher multiplier to account for deduplication
                        if needed <= 5:
                            # For small requests, fetch at least 15 with 3x multiplier
                            fetch_size = min(50, max(15, needed * 3))
                        else:
                            # For larger requests, use 2.5x buffer
                            fetch_size = min(50, int(needed * 2.5))

                        logger.debug(f"Fetching {fetch_size} companies from Apollo (page {page}, need {needed} more unique)")

                        # Fetch preview data from Apollo with circuit breaker and rate limiting
                        try:
                            async def _fetch_with_protection():
                                await apollo_rate_limiter.wait_for_token()
                                return await client.search_companies_preview(
                                    industry=industry,
                                    location=location,
                                    max_results=fetch_size,
                                    company_size=filters.get('company_size'),
                                    keywords=filters.get('keywords'),
                                    page=page
                                )

                            raw_companies = await apollo_breaker.call_async(_fetch_with_protection)
                        except CircuitBreakerError as e:
                            logger.error(f"Apollo API circuit breaker is open: {e}")
                            break

                        if not raw_companies:
                            logger.info(f"No more companies available from Apollo (page {page})")
                            break

                        # Track how many new leads we add in this iteration
                        leads_before = len(all_preview_leads)

                        # Filter duplicates
                        for company in raw_companies:
                            company_name = company.get('company_name', '')
                            normalized_name = normalize_company_name(company_name)

                            # Skip if already in database
                            if normalized_name in existing_names:
                                duplicates_filtered += 1
                                logger.info(f"✓ Filtered duplicate from DB: '{company_name}' (normalized: '{normalized_name}')")
                                continue

                            # Skip if already in internal DB results
                            if normalized_name in internal_db_names:
                                duplicates_filtered += 1
                                logger.debug(f"Filtered duplicate (already from internal DB): {company_name}")
                                continue

                            # Skip if already in current results
                            current_names = {normalize_company_name(l.company_name) for l in all_preview_leads}
                            if normalized_name in current_names:
                                duplicates_filtered += 1
                                logger.debug(f"Filtered duplicate in batch: {company_name}")
                                continue

                            # Create preview lead object with Apollo source marker
                            try:
                                company['lead_source'] = 'apollo'
                                preview_lead = ApolloPreviewLead(**company)
                                all_preview_leads.append(preview_lead)
                                apollo_count += 1

                                if len(all_preview_leads) >= max_results:
                                    break
                            except Exception as e:
                                logger.debug(f"Error creating preview lead: {e}")
                                continue

                        leads_added = len(all_preview_leads) - leads_before
                        logger.info(f"Page {page}: Added {leads_added} new leads, {len(all_preview_leads)}/{max_results} total, {duplicates_filtered} duplicates filtered")

                        # Break if we have enough leads
                        if len(all_preview_leads) >= max_results:
                            break

                        # Move to next page
                        page += 1

                    logger.info(f"🔍 Apollo: Found {apollo_count} additional leads")

            # Finalize response
            final_leads = all_preview_leads[:max_results]
            response.status = "completed"
            response.leads = final_leads
            response.total_found = len(final_leads)
            response.completed_at = datetime.now(timezone.utc)
            response.duration_seconds = (response.completed_at - response.started_at).total_seconds()

            # Cache successful response
            cache.store_apollo_search(
                location=location,
                industry=industry,
                max_results=max_results,
                results=response.dict(),
                **filters
            )

            # Log stats with source breakdown
            logger.info(
                f"Preview search completed: {len(final_leads)} total leads "
                f"(internal_db: {internal_db_count}, apollo: {apollo_count})"
            )

            return response

        except Exception as e:
            logger.error(f"Preview search failed: {e}")
            response = ApolloPreviewResponse(
                status="failed",
                message=str(e),
                started_at=start_time,
                completed_at=datetime.now(timezone.utc)
            )
            response.errors.append(str(e))
            return response

    async def enrich_selected_emails(
        self,
        company_ids: List[str],
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None,
        companies: Optional[List[Dict[str, Any]]] = None
    ):
        """
        STAGE 2: Enrich selected preview leads with email contacts only.

        Only fetches:
        - Decision maker name
        - Decision maker email
        - Job title

        Does NOT fetch:
        - Phone numbers
        - Social profiles
        - Other expensive data

        Args:
            company_ids: List of Apollo company IDs to enrich
            job_titles: Specific job titles to target
            department: Department filter
            seniority_level: Seniority level filter

        Returns:
            ApolloEnrichmentResponse with enriched leads (email only)
        """
        from .schemas import ApolloEnrichmentResponse, ApolloEnrichedLead

        start_time = datetime.now(timezone.utc)

        try:
            # Initialize response
            response = ApolloEnrichmentResponse(
                status="in_progress",
                started_at=start_time
            )

            enriched_leads = []
            failed_count = 0

            # Create Apollo client
            async with ApolloClient(self.config) as client:
                # Enrich companies with email contacts
                enriched_data = await client.enrich_company_emails(
                    company_ids=company_ids,
                    companies=companies,
                    job_titles=job_titles,
                    department=department,
                    seniority_level=seniority_level
                )

                # Convert to enriched lead objects
                for data in enriched_data:
                    try:
                        enriched_lead = ApolloEnrichedLead(**data)
                        enriched_leads.append(enriched_lead)
                    except Exception as e:
                        logger.error(f"Error creating enriched lead: {e}")
                        failed_count += 1
                        continue

            # Finalize response
            response.status = "completed"
            response.leads = enriched_leads
            response.total_enriched = len(enriched_leads)
            response.failed_count = failed_count
            response.completed_at = datetime.now(timezone.utc)
            response.duration_seconds = (response.completed_at - response.started_at).total_seconds()

            logger.info(
                f"Enrichment completed: {len(enriched_leads)} successful, "
                f"{failed_count} failed out of {len(company_ids)} requested"
            )

            return response

        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            response = ApolloEnrichmentResponse(
                status="failed",
                message=str(e),
                started_at=start_time,
                completed_at=datetime.now(timezone.utc)
            )
            response.errors.append(str(e))
            return response


# Global service instance for compatibility with existing code
_apollo_service = None


def get_apollo_service():
    """Get the enrichment service instance.

    Returns ``ApolloLeadService`` when ``ENRICHMENT_PROVIDER=apollo``
    (default), falls back to ``LemlistLeadService`` when
    ``ENRICHMENT_PROVIDER=lemlist``.
    """
    global _apollo_service
    if _apollo_service is None:
        provider = os.getenv("ENRICHMENT_PROVIDER", "apollo").lower()
        if provider == "lemlist":
            from lemlist.service import LemlistLeadService
            _apollo_service = LemlistLeadService()
        else:
            _apollo_service = ApolloLeadService()
    return _apollo_service
