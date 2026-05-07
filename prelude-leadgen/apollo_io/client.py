"""
Apollo.io API client focused on essential lead data extraction.

Optimized for retrieving the four most important lead fields:
- Company name
- Contact name
- Contact email
- Website URL
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional

from .schemas import ApolloConfig, ApolloApiError

logger = logging.getLogger(__name__)


class ApolloClient:
    """
    Apollo.io API client optimized for essential lead data extraction.

    Focuses on retrieving high-quality contact information with minimal API calls.
    """

    def __init__(self, config: ApolloConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": config.api_key
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session is initialized."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(
                headers=self.base_headers,
                timeout=timeout
            )

    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def search_people_and_companies(
        self,
        industry: str,
        location: str,
        max_results: int = 50,
        company_size: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for people and companies using Apollo.io two-step process.

        1. Search companies by industry/location/size/keywords
        2. Find decision makers matching job titles/department/seniority
        3. Enrich contacts to unlock emails

        Args:
            industry: Industry category
            location: Geographic location
            max_results: Maximum results to return
            company_size: Employee range filter
            keywords: Additional search keywords
            job_titles: Specific job titles to target
            department: Department to target
            seniority_level: Seniority level to target
        """
        await self._ensure_session()

        logger.info(f"Apollo search: {industry} in {location}")

        try:
            # Step 1: Search for companies with enhanced filters
            companies = await self._search_companies(
                industry=industry,
                location=location,
                max_results=max_results,
                keywords=keywords,
                company_size=company_size
            )
            if not companies:
                logger.warning("No companies found")
                return []

            logger.debug(f"Found {len(companies)} companies, searching for decision makers...")

            # Step 2: Find decision makers and enrich emails with enhanced filters
            leads = []
            for company in companies:
                if len(leads) >= max_results:
                    break

                company_leads = await self._get_company_decision_makers(
                    company=company,
                    job_titles=job_titles,
                    department=department,
                    seniority_level=seniority_level
                )
                leads.extend(company_leads)

                # Rate limiting
                await asyncio.sleep(0.1)

            logger.info(f"Apollo search completed: {len(leads)} leads")
            return leads[:max_results]

        except Exception as e:
            logger.error(f"❌ Apollo search failed: {e}")
            raise

    async def _search_companies(
        self,
        industry: str,
        location: str,
        max_results: int,
        keywords: Optional[List[str]] = None,
        company_size: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for companies using Apollo organizations endpoint with SIC codes.

        Args:
            industry: Industry category
            location: Geographic location
            max_results: Maximum results to return
            keywords: Additional search keywords for precision
            company_size: Employee range filter (e.g., "1-10", "11-50")
        """
        # Industry to SIC code mapping for precise filtering
        industry_sic_mapping = {
            "software": ["7372", "7371"],
            "healthcare": ["8062", "8071", "8092", "8093"],
            "automotive": ["3711", "3714", "5511"],
            "food": ["2099", "2098", "5411"],
            "construction": ["1542", "1611", "1623"],
            "manufacturing": ["3999", "3089", "3569"],
            "finance": ["6022", "6211", "6321"],
            "retail": ["5399", "5999", "5200"],
            "education": ["8221", "8331", "8299"],
            "consulting": ["8742", "8748", "8999"],
            "technology": ["7372", "7371"],  # Alias for software
        }

        url = f"{self.config.base_url}/v1/organizations/search"
        sic_codes = industry_sic_mapping.get(industry.lower())

        # Build base payload
        if sic_codes:
            # Use SIC codes for precise industry filtering
            payload = {
                "organization_sic_codes": sic_codes,
                "per_page": min(max_results, 25),
                "page": 1,
                "organization_locations": [location]
            }
        else:
            # Fallback to keyword search
            payload = {
                "q_keywords": industry,
                "per_page": min(max_results, 25),
                "page": 1,
                "organization_locations": [location]
            }

        # Add keywords for more specific targeting
        if keywords and len(keywords) > 0:
            payload["q_organization_keyword_tags"] = keywords
            logger.debug(f"Adding keywords filter: {keywords}")

        # Add company size filter
        if company_size:
            # Map size to Apollo format: "min,max"
            size_mapping = {
                "1-10": "1,10",
                "11-50": "11,50",
                "51-200": "51,200",
                "201-1000": "201,1000",
                "1000+": "1001,1000000"
            }
            if company_size in size_mapping:
                payload["organization_num_employees_ranges"] = [size_mapping[company_size]]
                logger.debug(f"Adding company size filter: {company_size}")

        logger.debug(f"Searching companies with payload: {payload}")

        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                companies = data.get('organizations', [])
                logger.debug(f"Found {len(companies)} companies")
                return companies
            else:
                error_text = await response.text()
                logger.error(f"Company search failed {response.status}: {error_text}")
                raise ApolloApiError(f"Company search failed: {error_text}", status_code=response.status)

    async def get_saved_contacts_for_company(
        self,
        company_name: str,
        company_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get contacts previously saved/enriched for a company.

        These contacts won't appear in people search results (to prevent duplicate
        enrichment charges), but you already have access to their emails.

        Args:
            company_name: Name of the company
            company_id: Optional Apollo company ID for additional filtering

        Returns:
            List of saved contact dictionaries with emails
        """
        url = f"{self.config.base_url}/v1/contacts/search"

        payload = {
            "q_keywords": company_name,
            "per_page": 50
        }

        try:
            await self._ensure_session()
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    contacts = data.get('contacts', [])

                    # Filter to exact company match
                    normalized_search = company_name.lower().strip()
                    company_contacts = []

                    for contact in contacts:
                        org_name = contact.get('organization_name', '')
                        if normalized_search in org_name.lower():
                            company_contacts.append(contact)

                    logger.info(f"📋 Found {len(company_contacts)} saved contacts for {company_name}")
                    return company_contacts
                else:
                    logger.debug(f"Saved contacts search failed: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching saved contacts: {e}")
            return []

    async def _get_company_decision_makers(
        self,
        company: Dict[str, Any],
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find decision makers in a specific company and enrich their emails.

        Priority:
        1. Check saved contacts first (already enriched, no cost)
        2. Search for new people and enrich if needed

        Args:
            company: Company data from Apollo
            job_titles: Specific job titles to target
            department: Department filter
            seniority_level: Seniority level filter
        """
        company_id = company.get('id')
        company_name = company.get('name', 'Unknown')

        if not company_id:
            return []

        # Helper function to prioritize by title importance
        def get_title_priority(title: str) -> int:
            """Calculate title importance (higher = more important)"""
            if not title:
                return 0

            title_lower = title.lower()

            # C-Level & Owners (highest priority)
            if any(x in title_lower for x in ['owner', 'founder', 'ceo', 'chief executive', 'president']):
                return 100

            # Other C-Level
            if any(x in title_lower for x in ['cfo', 'cto', 'cmo', 'coo', 'chief']):
                return 90

            # VP level
            if 'vp' in title_lower or 'vice president' in title_lower:
                return 80

            # Director level
            if 'director' in title_lower:
                return 70

            # Manager level
            if 'manager' in title_lower or 'head of' in title_lower:
                return 60

            # Other roles
            return 50

        # STEP 1: Check saved contacts first
        logger.info(f"🔍 Step 1: Checking saved contacts for {company_name}")
        saved_contacts = await self.get_saved_contacts_for_company(company_name, company_id)

        if saved_contacts:
            logger.info(f"✅ Found {len(saved_contacts)} saved contacts - no enrichment needed!")

            # Prioritize saved contacts by title
            sorted_saved = sorted(
                saved_contacts,
                key=lambda c: get_title_priority(c.get('title', '')),
                reverse=True
            )

            best_saved = sorted_saved[0]

            logger.info(f"✅ Using saved contact: {best_saved.get('name')} ({best_saved.get('title')}) - {best_saved.get('email')}")

            # Build lead data from saved contact
            contact_name = best_saved.get('name') or f"{best_saved.get('first_name', '')} {best_saved.get('last_name', '')}".strip()

            lead_data = {
                "company_name": company_name,
                "contact_name": contact_name,
                "contact_email": best_saved.get('email'),
                "contact_phone": best_saved.get('phone'),
                "title": best_saved.get('title'),
                "website": company.get('website_url') or company.get('primary_domain'),
                "industry": company.get('industry'),
                "location": self._extract_company_location(company),
                "apollo_person_id": best_saved.get('id'),
                "apollo_company_id": company_id,
                "final_score": 100  # Saved contact = maximum confidence
            }

            return [lead_data] if self._is_valid_lead(lead_data) else []

        # STEP 2: No saved contacts, search for new people
        logger.info("🔍 Step 2: No saved contacts, searching for new people...")

        # Search for decision makers
        url = f"{self.config.base_url}/v1/mixed_people/api_search"

        # Determine titles to search for
        if job_titles and len(job_titles) > 0:
            # Use user-specified job titles
            search_titles = job_titles
            logger.debug(f"Using custom job titles: {search_titles}")
        elif department:
            # Map department to relevant titles
            department_titles = self._get_department_titles(department)
            search_titles = department_titles
            logger.debug(f"Using department-based titles for {department}: {search_titles}")
        else:
            # Default decision maker titles
            search_titles = [
                "CEO", "CTO", "CMO", "CFO", "COO", "President", "VP", "Vice President",
                "Director", "Manager", "Head of", "Chief",
                "Owner", "Founder", "Co-Founder", "Partner"
            ]

        payload = {
            "organization_ids": [company_id],
            "person_titles": search_titles,
            "per_page": 3
        }

        # Add seniority filter if specified
        if seniority_level:
            payload["person_seniorities"] = [seniority_level]
            logger.debug(f"Adding seniority filter: {seniority_level}")

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    people = data.get('people', [])

                    logger.info(f"📋 Found {len(people)} people with title filter: {[(p.get('name') or 'Unknown') + ' (' + (p.get('title') or 'N/A') + ')' for p in people[:3]]}")

                    # ALWAYS do broader search to get people with emails (like "SHOP Owner")
                    # Title filter often misses people with actual email addresses
                    logger.info("🔍 Doing broader search without title filter to find more candidates...")
                    broad_payload = {
                        "organization_ids": [company_id],
                        "per_page": 10  # Get more results for filtering
                    }
                    if seniority_level:
                        broad_payload["person_seniorities"] = [seniority_level]

                    async with self.session.post(url, json=broad_payload) as broad_response:
                        if broad_response.status == 200:
                            broad_data = await broad_response.json()
                            broad_people = broad_data.get('people', [])
                            if broad_people:
                                logger.info(f"📋 Found {len(broad_people)} people without title filter: {[(p.get('name') or 'Unknown') + ' (' + (p.get('title') or 'N/A') + ')' for p in broad_people[:5]]}")
                                # Merge results, preferring people from title search but adding others
                                existing_ids = {p.get('id') for p in people}
                                for broad_person in broad_people:
                                    if broad_person.get('id') not in existing_ids:
                                        people.append(broad_person)
                                logger.info(f"📋 Total {len(people)} people after merging title + broad searches")
                        else:
                            error_text = await broad_response.text()
                            logger.error(f"❌ Broader search failed with status {broad_response.status}: {error_text}")
                            # Continue with just the title-filtered people

                    if not people:
                        return []

                    # Prioritize decision makers who already have real email addresses
                    # Filter out placeholder emails like "email_not_unlocked@domain.com"
                    def has_real_email(person):
                        email = person.get('email')
                        if not email:
                            return False
                        # Check for common placeholder patterns
                        if 'not_unlocked' in email.lower() or email.endswith('@domain.com'):
                            return False
                        return True

                    people_with_email = [p for p in people if has_real_email(p)]
                    people_without_email = [p for p in people if not has_real_email(p)]

                    logger.info(f"📧 {len(people_with_email)} people with real email, {len(people_without_email)} without")
                    if people_with_email:
                        logger.info(f"   With email: {[(p.get('name') or 'Unknown', p.get('email')) for p in people_with_email]}")
                    if people_without_email:
                        logger.info(f"   Without email: {[(p.get('name') or 'Unknown', p.get('email', 'None')) for p in people_without_email[:3]]}")

                    # Sort all people by title priority (highest priority first)
                    def person_sort_key(p):
                        has_email = has_real_email(p)
                        priority = get_title_priority(p.get('title', ''))
                        # Sort by: 1) has email (True > False), 2) priority (100 > 50)
                        return (has_email, priority)

                    sorted_people = sorted(people, key=person_sort_key, reverse=True)

                    logger.info("📊 Prioritized candidates:")
                    for p in sorted_people[:5]:
                        marker = "✅" if has_real_email(p) else "❌"
                        priority = get_title_priority(p.get('title', ''))
                        logger.info(f"   {marker} {p.get('name') or 'Unknown'} ({p.get('title') or 'N/A'}) - Priority: {priority}")

                    # Try enriching top 3 candidates (not just first one)
                    person = None
                    attempts = 0
                    max_attempts = 3

                    for candidate in sorted_people[:max_attempts]:
                        attempts += 1

                        if has_real_email(candidate):
                            # Already has email - use immediately
                            person = candidate
                            logger.info(f"✅ Selected #{attempts}: {person.get('name')} - already has email")
                            break
                        else:
                            # Try to enrich
                            person_id = candidate.get('id')
                            if person_id:
                                logger.info(f"🔓 Attempt #{attempts}: Enriching {candidate.get('name')} ({candidate.get('title')})")
                                enriched_person = await self._enrich_person_email(person_id)

                                if enriched_person and enriched_person.get('email'):
                                    candidate.update(enriched_person)

                                    # Check if enrichment was successful
                                    if has_real_email(candidate):
                                        person = candidate
                                        logger.info(f"✅ Success #{attempts}: Unlocked {person.get('email')}")
                                        break
                                    else:
                                        logger.warning(f"❌ Attempt #{attempts} failed: Still no email")

                    # Fallback to highest priority person even without email
                    if not person and sorted_people:
                        person = sorted_people[0]
                        logger.warning(f"⚠️ Using highest priority person without email: {person.get('name')}")

                    # Extract contact name
                    contact_name = self._extract_contact_name(person)
                    logger.debug(f"Contact extracted: '{contact_name}'")

                    # Build lead data
                    lead_data = {
                        "company_name": company_name,
                        "contact_name": contact_name,
                        "contact_email": person.get('email'),
                        "contact_phone": person.get('phone'),
                        "website": company.get('website_url') or company.get('primary_domain'),
                        "industry": company.get('industry'),
                        "location": self._extract_company_location(company),
                        "title": person.get('title'),
                        "apollo_person_id": person.get('id'),
                        "apollo_company_id": company_id,
                        "final_score": self._calculate_lead_score(
                            company_name,
                            contact_name,
                            person.get('email'),
                            company.get('website_url') or company.get('primary_domain')
                        )
                    }

                    # Validate lead before returning
                    if not self._is_valid_lead(lead_data):
                        logger.warning(f"❌ Lead rejected (no email/website): {company_name} - {contact_name}")
                        return []

                    return [lead_data]

                else:
                    logger.debug(f"No decision makers found for {company_name}")
                    return []

        except Exception as e:
            import traceback
            logger.error(f"❌ Error finding decision makers for {company_name}: {e}")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return []

    async def _enrich_person_email(self, person_id: str) -> Optional[Dict[str, Any]]:
        """
        Enrich person to unlock email (consumes credits).
        """
        url = f"{self.config.base_url}/v1/people/match"

        payload = {
            "id": person_id,
            "reveal_personal_emails": True
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('person', {})
                else:
                    logger.debug(f"Email enrichment failed for person {person_id}")
                    return None
        except Exception as e:
            logger.debug(f"Email enrichment error for person {person_id}: {e}")
            return None

    def _extract_company_location(self, company: Dict[str, Any]) -> Optional[str]:
        """
        Extract company location from company data.
        Tries multiple location fields in Apollo's response.
        """
        # Try primary_location first (most reliable)
        primary_location = company.get('primary_location', {})
        if primary_location:
            city = primary_location.get('city')
            state = primary_location.get('state')
            country = primary_location.get('country')

            if city and state:
                return f"{city}, {state}"
            elif city and country:
                return f"{city}, {country}"
            elif city:
                return city

        # Try organization fields as fallback
        org_city = company.get('city')
        org_state = company.get('state')
        org_country = company.get('country')

        if org_city and org_state:
            return f"{org_city}, {org_state}"
        elif org_city and org_country:
            return f"{org_city}, {org_country}"
        elif org_city:
            return org_city

        # Try headquarters_location
        hq_location = company.get('headquarters_location')
        if hq_location:
            return hq_location

        return None

    def _get_department_titles(self, department: str) -> List[str]:
        """Map department to relevant job titles for Apollo search."""
        department_mapping = {
            "sales": [
                "VP Sales", "Director of Sales", "Sales Manager", "Head of Sales",
                "Account Executive", "Business Development", "SDR", "Sales Representative"
            ],
            "marketing": [
                "CMO", "VP Marketing", "Marketing Director", "Marketing Manager",
                "Head of Marketing", "Brand Manager", "Product Marketing", "Growth Marketing"
            ],
            "engineering": [
                "CTO", "VP Engineering", "Engineering Manager", "Head of Engineering",
                "Software Engineer", "Tech Lead", "Director of Engineering", "Development Manager"
            ],
            "finance": [
                "CFO", "VP Finance", "Finance Director", "Controller",
                "Financial Analyst", "Accounting Manager", "Finance Manager"
            ],
            "hr": [
                "CHRO", "VP HR", "HR Director", "HR Manager", "People Operations",
                "Talent Acquisition", "Recruiting Manager", "Head of People"
            ],
            "operations": [
                "COO", "VP Operations", "Operations Manager", "Head of Operations",
                "Operations Director", "Process Manager"
            ],
            "product": [
                "CPO", "VP Product", "Product Manager", "Head of Product",
                "Product Director", "Product Lead"
            ],
            "customer_success": [
                "VP Customer Success", "Customer Success Manager", "Head of Customer Success",
                "Support Manager", "Client Success"
            ]
        }
        return department_mapping.get(department, [])

    def _extract_contact_name(self, person: Dict[str, Any]) -> Optional[str]:
        """Extract contact person name."""
        first_name = person.get("first_name", "")
        last_name = person.get("last_name", "")

        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif last_name:
            return last_name
        else:
            return None

    def _calculate_lead_score(
        self,
        company_name: Optional[str],
        contact_name: Optional[str],
        contact_email: Optional[str],
        website: Optional[str]
    ) -> int:
        """
        Calculate lead quality score.

        Scoring: company_name=40, contact_email=30, contact_name=20, website=10.
        """
        score = 0
        if company_name:
            score += 40
        if contact_email:
            score += 30
        if contact_name:
            score += 20
        if website:
            score += 10
        return min(score, 100)

    def _is_valid_lead(self, lead_data: Dict[str, Any]) -> bool:
        """Check if lead data is valid."""
        return bool(lead_data.get("company_name")) and (
            bool(lead_data.get("contact_email")) or bool(lead_data.get("website"))
        )

    # ===== TWO-STAGE WORKFLOW METHODS =====

    async def search_companies_preview(
        self,
        industry: str,
        location: str,
        max_results: int,
        company_size: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        STAGE 1: Preview search - company data only (cheap).

        Returns basic company info without contact enrichment:
        - Company name, website, industry, location
        - Employee count, revenue estimate, description
        - NO emails, NO decision maker details, NO phone

        This is significantly cheaper than full enrichment.

        Args:
            industry: Industry category
            location: Geographic location
            max_results: Maximum results to return
            company_size: Employee range filter
            keywords: Additional search keywords
            page: Page number for pagination (for retry logic)

        Returns:
            List of company data dictionaries (preview only)
        """
        await self._ensure_session()

        logger.info(f"Apollo preview search: {industry} in {location} (page {page})")

        # Use existing _search_companies method
        companies = await self._search_companies(
            industry=industry,
            location=location,
            max_results=max_results,
            keywords=keywords,
            company_size=company_size
        )

        if not companies:
            logger.warning("No companies found for preview search")
            return []

        # Transform to preview format (no contact details)
        preview_leads = []
        for company in companies:
            try:
                preview_lead = {
                    "apollo_company_id": company.get('id'),
                    "company_name": company.get('name', ''),
                    "website": company.get('website_url') or company.get('primary_domain'),
                    "industry": company.get('industry'),
                    "location": self._extract_company_location(company),
                    "employee_count": company.get('estimated_num_employees'),
                    "revenue_estimate": company.get('annual_revenue'),
                    "description": company.get('short_description') or company.get('description'),
                    # NO contact fields
                }

                # Only include if has company ID and name
                if preview_lead["apollo_company_id"] and preview_lead["company_name"]:
                    preview_leads.append(preview_lead)

            except Exception as e:
                logger.debug(f"Error transforming company {company.get('name', 'Unknown')}: {e}")
                continue

        logger.info(f"Apollo preview search completed: {len(preview_leads)} companies")
        return preview_leads

    async def enrich_company_emails(
        self,
        company_ids: List[str],
        companies: Optional[List[Dict[str, Any]]] = None,
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        STAGE 2: Enrich selected companies with contact emails ONLY (no phone).

        For each company:
        - Find decision makers matching criteria
        - Unlock email addresses ONLY
        - NO phone numbers, NO LinkedIn profiles

        This is expensive but user-controlled.

        Args:
            company_ids: List of Apollo company IDs to enrich
            companies: Optional list of full company data (for Google Maps → Apollo hybrid lookup)
            job_titles: Specific job titles to target
            department: Department filter
            seniority_level: Seniority level filter

        Returns:
            List of enriched lead data dictionaries (email only)
        """
        await self._ensure_session()

        logger.info(f"Enriching {len(company_ids)} companies with email contacts")

        enriched_leads = []
        companies = companies or []

        for idx, company_id in enumerate(company_ids):
            try:
                # Check if this is a Google Maps company (UUID format indicates it's not from Apollo)
                company_meta = companies[idx] if idx < len(companies) else None
                company_data = None
                original_company_name = None  # Track original name for matching

                # HYBRID APPROACH: If source is google_maps, search Apollo by name first
                if company_meta and company_meta.get('source') == 'google_maps':
                    company_name = company_meta.get('company_name', '')
                    original_company_name = company_name  # Save original Google Maps name
                    location = company_meta.get('location', '')
                    logger.info(f"🔍 Google Maps company detected: {company_name} in {location} - searching Apollo...")

                    url = f"{self.config.base_url}/v1/organizations/search"
                    await self._ensure_session()

                    # Import enhanced normalization with location suffix stripping
                    from database.queries import get_company_name_variants

                    # Create variations of the company name
                    original_name = company_name

                    # Get progressive name variants (exact and core)
                    name_variants = get_company_name_variants(company_name)
                    # name_variants = [("towlift", "exact"), ("towlift", "core")]

                    # Also try with ampersand variations
                    name_and_variant = original_name.replace('&', 'and') if '&' in original_name else None
                    name_ampersand_variant = original_name.replace(' and ', ' & ') if ' and ' in original_name else None

                    # Extract city from full address
                    # Format: "Street, City, State ZIP, Country"
                    # Example: "7501 Detour Ave, Cleveland, OH 44103, USA"
                    city = None
                    if location and ',' in location:
                        parts = [p.strip() for p in location.split(',')]
                        if len(parts) >= 2:
                            # Second part is usually the city
                            city = parts[1]
                            # Remove any state/ZIP from city if present
                            city = city.split()[0] if city else None

                    # Multi-strategy search with fuzzy matching
                    # CRITICAL: Try WITHOUT location FIRST - Google Maps city often doesn't match Apollo's city
                    # Example: "Cleveland" from Google Maps vs "Strongsville" in Apollo
                    company_data = None
                    strategies = []

                    # Strategy 1: Exact match WITHOUT location (most reliable!)
                    strategies.append(("exact, no location", original_name, None))

                    # Strategy 2: Progressive normalization variants WITHOUT location
                    # Try all name variants (exact normalized, then core with location suffix stripped)
                    for variant_name, variant_type in name_variants:
                        if variant_name != original_name:
                            strategies.append((f"{variant_type} normalized, no location", variant_name, None))

                    # Strategy 3: Ampersand variants WITHOUT location
                    if name_and_variant:
                        strategies.append(("'and' variant, no location", name_and_variant, None))
                    if name_ampersand_variant:
                        strategies.append(("'&' variant, no location", name_ampersand_variant, None))

                    # Strategy 4: Exact match WITH location (fallback only)
                    if city:
                        strategies.append(("exact + location", original_name, city))

                    # Strategy 5: Progressive normalization variants WITH location
                    if city:
                        for variant_name, variant_type in name_variants:
                            if variant_name != original_name:
                                strategies.append((f"{variant_type} normalized + location", variant_name, city))

                    # Strategy 6: Ampersand variants WITH location
                    if name_and_variant and city:
                        strategies.append(("'and' variant + location", name_and_variant, city))
                    if name_ampersand_variant and city:
                        strategies.append(("'&' variant + location", name_ampersand_variant, city))

                    for strategy_name, search_name, search_city in strategies:
                        if not search_name:
                            continue

                        # Use q_organization_name for company name search.
                        # Always scope Apollo's org search to US companies — the
                        # two-pager / BoL use cases are US importers, and
                        # letting Apollo return foreign matches (e.g., an Indian
                        # "Visual Creation" firm for a US watch importer) sends
                        # emails to the wrong company.
                        locations = ["united states"]
                        if search_city:
                            locations.append(search_city)
                        search_params = {
                            "q_organization_name": search_name,
                            "per_page": 5,  # Increased to get more candidates
                            "organization_locations": locations,
                        }

                        logger.info(f"🔎 Strategy: {strategy_name} | Name: '{search_name}' | City: {search_city or 'none'}")

                        async with self.session.post(url, json=search_params) as response:
                            if response.status == 200:
                                search_result = await response.json()
                                if search_result and search_result.get('organizations'):
                                    logger.info(f"📋 Apollo returned {len(search_result.get('organizations', []))} orgs: {[org.get('name') for org in search_result.get('organizations', [])[:3]]}")
                                if search_result and search_result.get('organizations'):
                                    # Use shared normalization function for consistency
                                    from database.queries import normalize_company_name
                                    search_normalized = normalize_company_name(search_name).lower()

                                    # Extract state from Google Maps location for prioritization
                                    # Format: "Street, City, State ZIP, Country"
                                    google_state = None
                                    if location and ',' in location:
                                        parts = [p.strip() for p in location.split(',')]
                                        if len(parts) >= 3:
                                            # Third part usually has state and ZIP
                                            state_part = parts[2].strip().split()[0] if parts[2] else None
                                            if state_part and len(state_part) == 2:
                                                google_state = state_part.upper()

                                    # Collect all matching candidates with location scores
                                    candidates = []

                                    # Multi-level fuzzy matching with progressive normalization
                                    for org in search_result['organizations']:
                                        org_name = org.get('name', '')

                                        # Get all normalization variants for the organization name
                                        org_variants = get_company_name_variants(org_name)
                                        org_normalized = org_variants[0][0] if org_variants else org_name.lower()

                                        match_type = None
                                        match_ratio = 0

                                        # Level 1: Exact normalized match
                                        if org_normalized == search_normalized:
                                            match_type = "exact"
                                            match_ratio = 1.0
                                        else:
                                            # Level 2: Try matching against all variants (including core name)
                                            for org_variant, variant_type in org_variants:
                                                if org_variant == search_normalized:
                                                    match_type = f"{variant_type}_match"
                                                    match_ratio = 0.95 if variant_type == "core" else 1.0
                                                    break

                                        # Level 3: Partial match with word overlap check (fallback)
                                        if not match_type:
                                            if search_normalized in org_normalized or org_normalized in search_normalized:
                                                search_words = set(search_normalized.split())
                                                org_words = set(org_normalized.split())
                                                common_words = search_words.intersection(org_words)
                                                match_ratio = len(common_words) / max(len(search_words), len(org_words)) if search_words or org_words else 0

                                                if match_ratio >= 0.7:
                                                    match_type = "partial"

                                        if match_type:
                                            # Calculate location score
                                            org_city = (org.get('city') or '').lower()
                                            org_state = (org.get('state') or '').upper()
                                            org_country = (org.get('country') or '').strip().lower()

                                            # Belt-and-suspenders US gate: the
                                            # organization_locations pre-filter
                                            # should have caught this, but
                                            # reject any non-US org that slips
                                            # through. Empty country passes
                                            # (Apollo sometimes omits).
                                            _US_COUNTRY_VALUES = {"united states", "usa", "us", "united states of america"}
                                            if org_country and org_country not in _US_COUNTRY_VALUES:
                                                logger.info(f"   ⏭ Skipping non-US match: '{org_name}' in {org_country}")
                                                continue

                                            location_score = 0

                                            # Prioritize same state
                                            if google_state and org_state == google_state:
                                                location_score = 2
                                            # Then same city
                                            if city and org_city == city.lower():
                                                location_score += 1

                                            candidates.append({
                                                'org': org,
                                                'match_type': match_type,
                                                'match_ratio': match_ratio,
                                                'location_score': location_score,
                                                'org_name': org_name,
                                                'org_city': org_city,
                                                'org_state': org_state
                                            })

                                    # Sort candidates: prioritize by location_score, then match_ratio
                                    if candidates:
                                        candidates.sort(key=lambda x: (x['location_score'], x['match_ratio']), reverse=True)
                                        best_match = candidates[0]
                                        company_data = best_match['org']

                                        location_info = f"{best_match['org_city']}, {best_match['org_state']}" if best_match['org_city'] or best_match['org_state'] else "unknown location"
                                        logger.info(f"✅ Best match ({best_match['match_type']})! '{best_match['org_name']}' in {location_info} (location_score: {best_match['location_score']}, match: {best_match['match_ratio']*100:.0f}%, org_id: {company_data.get('id')})")

                                        if len(candidates) > 1:
                                            logger.info(f"   Found {len(candidates)} candidates, chose best based on location+match score")

                                    if company_data:
                                        break
                                    else:
                                        # Log what we got for debugging
                                        logger.debug(f"No match in results: {[org.get('name') for org in search_result['organizations'][:3]]}")
                            else:
                                logger.error(f"Apollo search failed with status {response.status}")

                        if company_data:
                            break

                    if not company_data:
                        logger.warning(f"❌ No Apollo match found for '{company_name}' after trying {len(strategies)} strategies")
                        continue
                else:
                    # Original Apollo flow - lookup by ID
                    company_data = await self._get_company_by_id(company_id)

                if not company_data:
                    logger.warning(f"Company {company_id} not found")
                    continue

                # Find decision makers (reuse existing method)
                decision_makers = await self._get_company_decision_makers(
                    company=company_data,
                    job_titles=job_titles,
                    department=department,
                    seniority_level=seniority_level
                )

                if decision_makers:
                    # Take the first decision maker
                    dm = decision_makers[0]

                    enriched_lead = {
                        "apollo_company_id": company_id,
                        "company_name": dm.get("company_name"),  # Apollo's canonical name
                        "original_company_name": original_company_name,  # Original Google Maps name for matching
                        "website": dm.get("website"),
                        "industry": dm.get("industry"),
                        "location": dm.get("location"),
                        "contact_name": dm.get("contact_name"),
                        "contact_email": dm.get("contact_email"),
                        "contact_title": dm.get("title"),
                        "apollo_person_id": dm.get("apollo_person_id"),
                        "final_score": dm.get("final_score", 50),
                        # NO phone field
                    }

                    logger.info(f"✅ Enriched {dm.get('company_name')}: {dm.get('contact_name')} <{dm.get('contact_email')}>")
                    enriched_leads.append(enriched_lead)
                else:
                    # No decision makers found - don't add to enriched_leads
                    # This will be handled as a failed enrichment by main.py
                    logger.warning(f"⚠️ No decision makers found for {company_data.get('name')} - skipping")

                # Rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error enriching company {company_id}: {e}")
                continue

        logger.info(f"Enrichment completed: {len(enriched_leads)}/{len(company_ids)} successful")

        # Lemlist fallback removed 2026-04-25: the previous implementation
        # called `LemlistClient()` with no args, which threw `__init__()
        # missing 1 required positional argument: 'config'` on every Apollo
        # call and was caught + logged as a warning. It never actually
        # recovered any misses. The two-pager is Apollo-only by policy
        # (importyeti/reports/two_pager_service.py:31), so leaving the fallback
        # here served no purpose besides log noise.
        return enriched_leads

    async def _get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Fetch company data by Apollo ID."""
        url = f"{self.config.base_url}/v1/organizations/{company_id}"

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('organization', {})
                else:
                    logger.debug(f"Company {company_id} not found")
                    return None
        except Exception as e:
            logger.error(f"Error fetching company {company_id}: {e}")
            return None