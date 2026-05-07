"""
LinkedIn scraping services.

Business logic for LinkedIn profile scraping, company research,
and personnel data extraction with compliance and rate limiting.
"""

import asyncio
import logging
import random
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote

from ..utils import (
    LeadGenBaseException,
    ExternalServiceError,
    ValidationError,
    DataQualityError,
    OperationTimeoutError,
    RateLimitError,
    clean_text,
    clean_phone,
    clean_email,
    clean_website,
    normalize_company_name,
    calculate_data_quality_score,
    calculate_lead_priority_score,
    remove_duplicates_by_key,
    get_current_timestamp,
    random_delay,
    generate_unique_id,
    truncate_text
)

from .schemas import (
    LinkedInSearchRequest,
    LinkedInSearchResponse,
    LinkedInScrapeRequest,
    LinkedInBatchRequest,
    LinkedInProfile,
    LinkedInSearchResult,
    PersonnelData,
    CompanyProfile,
    CompanyResearchRequest,
    LinkedInJobMetrics,
    LinkedInEnrichmentRequest,
    WorkExperience,
    Education,
    Certification,
    LinkedInJobStatus,
    ScrapeReason,
    ProfilePrivacyLevel,
    ConnectionLevel
)

logger = logging.getLogger(__name__)


class LinkedInScrapingError(ExternalServiceError):
    """Specific exception for LinkedIn scraping errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message, service="linkedin", error_code=error_code)


class LinkedInRateLimitError(RateLimitError):
    """LinkedIn-specific rate limiting error."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, service="linkedin", retry_after=retry_after)


class LinkedInService:
    """
    Service for LinkedIn profile scraping and company research.
    
    Handles search operations, profile extraction, and data enrichment
    with proper rate limiting, compliance, and error handling.
    """
    
    def __init__(self):
        self.active_jobs: Dict[str, LinkedInJobMetrics] = {}
        self.rate_limit_tracker = {
            'requests': 0,
            'window_start': datetime.now(timezone.utc),
            'requests_per_hour': 100  # Conservative rate limit
        }
        
        # LinkedIn scraping configuration
        self.config = {
            'min_delay': 2.0,  # Minimum delay between requests
            'max_delay': 5.0,  # Maximum delay between requests
            'max_retries': 3,
            'timeout_seconds': 30,
            'batch_size': 10,  # Process profiles in batches
            'compliance_mode': True  # Enhanced compliance checking
        }
        
    async def search_profiles(
        self,
        search_request: LinkedInSearchRequest,
        job_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> LinkedInSearchResponse:
        """
        Search for LinkedIn profiles based on criteria.
        
        Args:
            search_request: Search parameters
            job_id: Optional job identifier for tracking
            user_id: User initiating the search
            
        Returns:
            Search response with results and scraped profiles
            
        Raises:
            LinkedInScrapingError: If search fails
            LinkedInRateLimitError: If rate limited
        """
        if not job_id:
            job_id = generate_unique_id("linkedin_search")
            
        # Check rate limits
        await self._check_rate_limits()
        
        # Create job metrics
        job_metrics = LinkedInJobMetrics(
            job_id=job_id,
            status=LinkedInJobStatus.RUNNING,
            total_profiles_requested=search_request.num_results,
            started_at=get_current_timestamp()
        )
        self.active_jobs[job_id] = job_metrics
        
        try:
            logger.info(f"Starting LinkedIn search: {search_request.company_name} - {search_request.role_name}")
            
            # Execute search
            search_results = await self._execute_search(search_request)
            
            profiles = []
            if search_request.scrape_profiles:
                # Scrape profiles from search results
                profile_urls = [result.profile_url for result in search_results]
                scrape_request = LinkedInScrapeRequest(
                    profile_urls=profile_urls,
                    scrape_reason=search_request.scrape_reason
                )
                profiles = await self._scrape_profiles(scrape_request, job_metrics)
            
            # Calculate success rate
            success_rate = len(profiles) / len(search_results) if search_results else 0.0
            
            # Create response
            response = LinkedInSearchResponse(
                status="completed",
                search_request=search_request,
                results=search_results,
                total_found=len(search_results),
                profiles=profiles,
                success_rate=success_rate,
                completed_at=get_current_timestamp(),
                started_at=job_metrics.started_at
            )
            
            # Update job metrics
            job_metrics.status = LinkedInJobStatus.COMPLETED
            job_metrics.profiles_processed = len(profiles)
            job_metrics.completed_at = get_current_timestamp()
            job_metrics.progress_percentage = 100.0
            
            logger.info(f"LinkedIn search completed: {len(profiles)} profiles scraped")
            return response
            
        except Exception as e:
            job_metrics.status = LinkedInJobStatus.FAILED
            job_metrics.completed_at = get_current_timestamp()
            
            logger.error(f"LinkedIn search failed: {e}")
            raise LinkedInScrapingError(f"Search failed: {str(e)}")
    
    async def scrape_profiles(
        self,
        scrape_request: LinkedInScrapeRequest,
        job_id: Optional[str] = None
    ) -> List[LinkedInProfile]:
        """
        Scrape LinkedIn profiles directly from URLs.
        
        Args:
            scrape_request: Scrape parameters and URLs
            job_id: Optional job identifier
            
        Returns:
            List of scraped profiles
            
        Raises:
            LinkedInScrapingError: If scraping fails
        """
        if not job_id:
            job_id = generate_unique_id("linkedin_scrape")
        
        job_metrics = LinkedInJobMetrics(
            job_id=job_id,
            status=LinkedInJobStatus.RUNNING,
            total_profiles_requested=len(scrape_request.profile_urls),
            started_at=get_current_timestamp()
        )
        self.active_jobs[job_id] = job_metrics
        
        try:
            profiles = await self._scrape_profiles(scrape_request, job_metrics)
            
            job_metrics.status = LinkedInJobStatus.COMPLETED
            job_metrics.completed_at = get_current_timestamp()
            job_metrics.progress_percentage = 100.0
            
            return profiles
            
        except Exception as e:
            job_metrics.status = LinkedInJobStatus.FAILED
            job_metrics.completed_at = get_current_timestamp()
            raise LinkedInScrapingError(f"Profile scraping failed: {str(e)}")
    
    async def research_company(
        self,
        request: CompanyResearchRequest,
        job_id: Optional[str] = None
    ) -> CompanyProfile:
        """
        Research a company on LinkedIn including employee profiles.
        
        Args:
            request: Company research parameters
            job_id: Optional job identifier
            
        Returns:
            Company profile with employee data
            
        Raises:
            LinkedInScrapingError: If research fails
        """
        if not job_id:
            job_id = generate_unique_id("linkedin_company")
        
        logger.info(f"Starting LinkedIn company research: {request.company_name}")
        
        try:
            # Mock company data for demonstration
            company_profile = await self._generate_mock_company_data(request)
            
            logger.info(f"Company research completed: {len(company_profile.employees)} employees found")
            return company_profile
            
        except Exception as e:
            logger.error(f"Company research failed: {e}")
            raise LinkedInScrapingError(f"Company research failed: {str(e)}")
    
    async def enrich_profiles(
        self,
        request: LinkedInEnrichmentRequest,
        job_id: Optional[str] = None
    ) -> List[PersonnelData]:
        """
        Enrich existing profile data with additional LinkedIn information.
        
        Args:
            request: Enrichment parameters
            job_id: Optional job identifier
            
        Returns:
            List of enriched personnel data
            
        Raises:
            LinkedInScrapingError: If enrichment fails
        """
        if not job_id:
            job_id = generate_unique_id("linkedin_enrich")
        
        logger.info(f"Starting profile enrichment for {len(request.profiles)} profiles")
        
        try:
            enriched_profiles = []
            
            for profile_data in request.profiles:
                # Mock enrichment process
                enriched = await self._enrich_single_profile(profile_data, request)
                enriched_profiles.append(enriched)
                
                # Rate limiting
                await random_delay(1.0, 2.0)
            
            logger.info(f"Profile enrichment completed: {len(enriched_profiles)} profiles enriched")
            return enriched_profiles
            
        except Exception as e:
            logger.error(f"Profile enrichment failed: {e}")
            raise LinkedInScrapingError(f"Profile enrichment failed: {str(e)}")
    
    async def _execute_search(
        self,
        search_request: LinkedInSearchRequest
    ) -> List[LinkedInSearchResult]:
        """Execute LinkedIn search operation (mock implementation)."""
        
        # Simulate search delay
        await asyncio.sleep(random.uniform(2, 4))
        
        # Generate mock search results
        results = []
        num_results = min(search_request.num_results, 20)  # Limit for demo
        
        for i in range(num_results):
            result = LinkedInSearchResult(
                profile_url=f"https://linkedin.com/in/person-{i+1}",
                name=f"{random.choice(['John', 'Jane', 'Mike', 'Sarah', 'David', 'Emma'])} {random.choice(['Smith', 'Johnson', 'Brown', 'Davis', 'Wilson', 'Taylor'])}",
                headline=f"{search_request.role_name} at {search_request.company_name}",
                location=search_request.location or "San Francisco Bay Area",
                current_company=search_request.company_name,
                current_position=search_request.role_name,
                connection_level=random.choice([ConnectionLevel.FIRST, ConnectionLevel.SECOND, ConnectionLevel.THIRD]),
                search_relevance=random.uniform(0.7, 1.0),
                search_position=i + 1
            )
            results.append(result)
        
        return results
    
    async def _scrape_profiles(
        self,
        scrape_request: LinkedInScrapeRequest,
        job_metrics: LinkedInJobMetrics
    ) -> List[LinkedInProfile]:
        """Scrape profile data from LinkedIn URLs (mock implementation)."""
        
        profiles = []
        
        for i, profile_url in enumerate(scrape_request.profile_urls):
            try:
                # Update job progress
                job_metrics.progress_percentage = (i / len(scrape_request.profile_urls)) * 100
                job_metrics.last_activity_at = get_current_timestamp()
                
                # Check rate limits
                await self._check_rate_limits()
                
                # Simulate profile scraping
                profile = await self._scrape_single_profile(
                    profile_url,
                    scrape_request.scrape_reason,
                    i + 1
                )
                
                if profile:
                    profiles.append(profile)
                    job_metrics.profiles_processed += 1
                    
                    # Count quality metrics
                    if profile.personnel_data.email:
                        job_metrics.profiles_with_email += 1
                    if profile.personnel_data.phone:
                        job_metrics.profiles_with_phone += 1
                else:
                    job_metrics.profiles_failed += 1
                
                # Rate limiting delay
                await random_delay(
                    self.config['min_delay'],
                    self.config['max_delay']
                )
                
            except Exception as e:
                logger.warning(f"Failed to scrape profile {profile_url}: {e}")
                job_metrics.profiles_failed += 1
                continue
        
        return profiles
    
    async def _scrape_single_profile(
        self,
        profile_url: str,
        scrape_reason: ScrapeReason,
        attempt_number: int
    ) -> Optional[LinkedInProfile]:
        """Scrape a single LinkedIn profile (mock implementation)."""
        
        # Simulate scraping delay
        await asyncio.sleep(random.uniform(1, 3))
        
        # Generate mock profile data
        names = ['John Smith', 'Jane Doe', 'Mike Johnson', 'Sarah Wilson', 'David Brown', 'Emma Davis']
        positions = ['Software Engineer', 'Product Manager', 'Data Scientist', 'Marketing Director', 'Sales Manager']
        companies = ['Tech Corp', 'Innovation Inc', 'Digital Solutions', 'Future Systems', 'Smart Tech']
        
        name = random.choice(names)
        first_name, last_name = name.split(' ', 1)
        
        # Create mock personnel data
        personnel_data = PersonnelData(
            full_name=name,
            first_name=first_name,
            last_name=last_name,
            headline=f"{random.choice(positions)} at {random.choice(companies)}",
            location=random.choice(['San Francisco, CA', 'New York, NY', 'Seattle, WA', 'Austin, TX']),
            about="Experienced professional with a passion for innovation and technology.",
            email=f"{first_name.lower()}.{last_name.lower()}@example.com" if random.random() > 0.3 else None,
            phone=f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}" if random.random() > 0.5 else None,
            current_company=random.choice(companies),
            current_position=random.choice(positions),
            industry="Technology",
            followers_count=random.randint(100, 5000),
            connections_count=random.randint(50, 500),
            connection_level=random.choice([ConnectionLevel.SECOND, ConnectionLevel.THIRD]),
            skills=['Python', 'Leadership', 'Project Management', 'Data Analysis'],
            languages=['English', 'Spanish'] if random.random() > 0.7 else ['English'],
            experience=[
                WorkExperience(
                    company=random.choice(companies),
                    position=random.choice(positions),
                    start_date="2020-01",
                    end_date=None,
                    is_current=True,
                    description="Leading innovative projects and driving business growth."
                )
            ],
            education=[
                Education(
                    institution="University of Technology",
                    degree="Bachelor of Science",
                    field_of_study="Computer Science",
                    start_year=2016,
                    end_year=2020
                )
            ]
        )
        
        # Calculate data quality
        quality_score = calculate_data_quality_score({
            'company': personnel_data.current_company,
            'email': personnel_data.email,
            'phone': personnel_data.phone,
            'industry': personnel_data.industry
        })
        
        lead_score = calculate_lead_priority_score({
            'company': personnel_data.current_company,
            'email': personnel_data.email,
            'phone': personnel_data.phone,
            'position': personnel_data.current_position
        })
        
        profile = LinkedInProfile(
            linkedin_url=profile_url,
            personnel_data=personnel_data,
            profile_completeness=quality_score,
            data_quality_score=quality_score,
            lead_score=lead_score,
            scraped_at=get_current_timestamp(),
            scrape_reason=scrape_reason,
            attempt_number=attempt_number,
            privacy_level=ProfilePrivacyLevel.SEMI_PRIVATE,
            memory_usage_mb=random.uniform(50, 150)
        )
        
        return profile
    
    async def _generate_mock_company_data(
        self,
        request: CompanyResearchRequest
    ) -> CompanyProfile:
        """Generate mock company profile data."""
        
        # Simulate research delay
        await asyncio.sleep(random.uniform(3, 6))
        
        # Generate employee profiles
        employees = []
        num_employees = min(request.employee_limit, 25)  # Limit for demo
        
        for i in range(num_employees):
            employee = PersonnelData(
                full_name=f"Employee {i+1}",
                first_name=f"First{i+1}",
                last_name=f"Last{i+1}",
                headline=f"Professional at {request.company_name}",
                current_company=request.company_name,
                current_position=random.choice(request.target_roles or ["Professional"]),
                email=f"employee{i+1}@{request.company_name.lower().replace(' ', '')}.com",
                industry="Technology"
            )
            employees.append(employee)
        
        company_profile = CompanyProfile(
            company_name=request.company_name,
            linkedin_url=f"https://linkedin.com/company/{request.company_name.lower().replace(' ', '-')}",
            website=f"https://www.{request.company_name.lower().replace(' ', '')}.com",
            industry="Technology",
            company_size="201-500 employees",
            headquarters="San Francisco, CA",
            founded_year=2010,
            description=f"{request.company_name} is a leading technology company.",
            specialties=["Innovation", "Technology", "Software Development"],
            followers_count=random.randint(1000, 10000),
            employees=employees,
            leadership_team=employees[:3],  # First 3 as leadership
            research_date=get_current_timestamp(),
            data_quality_score=85.0
        )
        
        return company_profile
    
    async def _enrich_single_profile(
        self,
        profile_data: Dict[str, Any],
        request: LinkedInEnrichmentRequest
    ) -> PersonnelData:
        """Enrich a single profile with additional data."""
        
        # Simulate enrichment delay
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Mock enrichment - add missing fields
        enriched_data = profile_data.copy()
        
        if 'email' not in enriched_data and request.verify_contact_info:
            enriched_data['email'] = f"enriched@example.com"
        
        if 'phone' not in enriched_data and request.verify_contact_info:
            enriched_data['phone'] = f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"
        
        if 'skills' not in enriched_data:
            enriched_data['skills'] = ['Leadership', 'Communication', 'Problem Solving']
        
        return PersonnelData(**enriched_data)
    
    async def _check_rate_limits(self):
        """Check and enforce rate limiting."""
        now = datetime.now(timezone.utc)
        
        # Reset window if an hour has passed
        if (now - self.rate_limit_tracker['window_start']).total_seconds() > 3600:
            self.rate_limit_tracker['requests'] = 0
            self.rate_limit_tracker['window_start'] = now
        
        # Check if we've exceeded the limit
        if self.rate_limit_tracker['requests'] >= self.rate_limit_tracker['requests_per_hour']:
            seconds_until_reset = 3600 - (now - self.rate_limit_tracker['window_start']).total_seconds()
            raise LinkedInRateLimitError(
                f"Rate limit exceeded. Try again in {int(seconds_until_reset)} seconds",
                retry_after=int(seconds_until_reset)
            )
        
        # Increment counter
        self.rate_limit_tracker['requests'] += 1
    
    async def get_job_status(self, job_id: str) -> Optional[LinkedInJobMetrics]:
        """Get the status of a LinkedIn scraping job."""
        return self.active_jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an active LinkedIn scraping job."""
        job = self.active_jobs.get(job_id)
        if job and job.status == LinkedInJobStatus.RUNNING:
            job.status = LinkedInJobStatus.CANCELLED
            job.completed_at = get_current_timestamp()
            logger.info(f"Cancelled LinkedIn job: {job_id}")
            return True
        return False
    
    async def cleanup_completed_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs."""
        cutoff_time = get_current_timestamp() - timedelta(hours=max_age_hours)
        
        to_remove = []
        for job_id, job in self.active_jobs.items():
            if (job.completed_at and job.completed_at < cutoff_time and 
                job.status in [LinkedInJobStatus.COMPLETED, LinkedInJobStatus.FAILED, LinkedInJobStatus.CANCELLED]):
                to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.active_jobs[job_id]
        
        logger.info(f"Cleaned up {len(to_remove)} old LinkedIn jobs")
        return len(to_remove)


# Global service instance
_linkedin_service: Optional[LinkedInService] = None


def get_linkedin_service() -> LinkedInService:
    """Get the global LinkedIn service instance."""
    global _linkedin_service
    if _linkedin_service is None:
        _linkedin_service = LinkedInService()
    return _linkedin_service