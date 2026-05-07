"""Lemlist API client — drop-in replacement for ApolloClient.

All public methods return the same dict shapes as their Apollo counterparts
so callers (service layer, lead_enrichment, two_pager) need zero changes.
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
from pydantic import BaseModel

from utils.rate_limiter import get_rate_limiter

from .enrichment_poller import EnrichmentPoller
from .filter_registry import FilterRegistry

logger = logging.getLogger(__name__)

lemlist_rate_limiter = get_rate_limiter("lemlist_api", rate_limit=20, time_period=2)


class LemlistConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.lemlist.com/api"
    timeout_seconds: int = 30


def _extract_domain(url: Optional[str]) -> Optional[str]:
    """Extract domain from a URL or return as-is if already a domain."""
    if not url:
        return None
    url = url.strip()
    match = re.match(r"https?://(?:www\.)?([^/]+)", url)
    if match:
        return match.group(1)
    if "." in url and " " not in url:
        return url.removeprefix("www.")
    return None


def _get_title_priority(title: str) -> int:
    """Rank title importance — mirrors ApolloClient logic."""
    if not title:
        return 0
    t = title.lower()
    if any(x in t for x in ["owner", "founder", "ceo", "chief executive", "president"]):
        return 100
    if any(x in t for x in ["cfo", "cto", "cmo", "coo", "chief"]):
        return 90
    if "vp" in t or "vice president" in t:
        return 80
    if "director" in t:
        return 70
    if "manager" in t or "head of" in t:
        return 60
    return 50


class LemlistClient:
    """Async HTTP client for the Lemlist API.

    Implements the same public interface as ``ApolloClient`` so it can be
    used as a drop-in replacement at the service & enrichment layers.
    """

    def __init__(self, config: LemlistConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self._auth = aiohttp.BasicAuth(login="", password=config.api_key)
        self._poller: Optional[EnrichmentPoller] = None
        self._filter_registry: Optional[FilterRegistry] = None
        self._database_api_available = True
        # Surfaced to callers (e.g. two-pager warnings) when Lemlist returns
        # a credit-exhaustion error on any enrich call during this session.
        self.credit_exhausted: bool = False

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(
                auth=self._auth,
                timeout=timeout,
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _get_poller(self) -> EnrichmentPoller:
        if self._poller is None:
            self._poller = EnrichmentPoller(self)
        return self._poller

    async def _get_filters(self) -> FilterRegistry:
        if self._filter_registry is None:
            self._filter_registry = await FilterRegistry.get_instance(self)
        return self._filter_registry

    # ------------------------------------------------------------------
    # Raw Lemlist endpoints
    # ------------------------------------------------------------------

    async def get_filters(self) -> List[Dict[str, Any]]:
        """GET /database/filters — discover available filter IDs."""
        await self._ensure_session()
        url = f"{self.config.base_url}/database/filters"
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.warning(f"GET /database/filters returned {resp.status}: {text[:200]}")
            return []

    async def search_companies(
        self,
        filters: List[Dict[str, Any]],
        page: int = 1,
        size: int = 100,
    ) -> Dict[str, Any]:
        """POST /database/companies — search the company database."""
        await self._ensure_session()
        if not self._database_api_available:
            return {"results": [], "total": 0, "limitation": 0}

        url = f"{self.config.base_url}/database/companies"
        body = {"filters": filters, "page": page, "size": size}
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.post(url, json=body) as resp:
            if resp.status == 403:
                self._database_api_available = False
                logger.error("Lemlist Database API returned 403 — may require plan upgrade")
                return {"results": [], "total": 0, "limitation": 0}
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"Lemlist company search {resp.status}: {text[:200]}")
                return {"results": [], "total": 0, "limitation": 0}
            return await resp.json()

    async def search_people(
        self,
        filters: List[Dict[str, Any]],
        search: Optional[str] = None,
        page: int = 1,
        size: int = 100,
    ) -> Dict[str, Any]:
        """POST /database/people — search the people database."""
        await self._ensure_session()
        if not self._database_api_available:
            return {"results": [], "total": 0, "limitation": 0}

        url = f"{self.config.base_url}/database/people"
        body: Dict[str, Any] = {"filters": filters, "page": page, "size": size}
        if search:
            body["search"] = search
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.post(url, json=body) as resp:
            if resp.status == 403:
                self._database_api_available = False
                logger.error("Lemlist People Database API returned 403 — may require plan upgrade")
                return {"results": [], "total": 0, "limitation": 0}
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"Lemlist people search {resp.status}: {text[:200]}")
                return {"results": [], "total": 0, "limitation": 0}
            return await resp.json()

    async def enrich_person(
        self,
        first_name: str,
        last_name: str,
        company_name: Optional[str] = None,
        company_domain: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        find_email: bool = True,
    ) -> Optional[str]:
        """POST /enrich — submit async enrichment. Returns enrichment ID."""
        await self._ensure_session()
        params: Dict[str, str] = {}
        if first_name:
            params["firstName"] = first_name
        if last_name:
            params["lastName"] = last_name
        if company_name:
            params["companyName"] = company_name
        if company_domain:
            params["companyDomain"] = company_domain
        if linkedin_url:
            params["linkedinUrl"] = linkedin_url
        if find_email:
            params["findEmail"] = "true"

        url = f"{self.config.base_url}/enrich?{urlencode(params)}"
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.post(url) as resp:
            if resp.status in (200, 201):
                data = await resp.json()
                return data.get("id")
            text = await resp.text()
            logger.warning(f"Lemlist enrich submit {resp.status}: {text[:200]}")
            if resp.status == 400 and "credit" in text.lower():
                self.credit_exhausted = True
            return None

    async def get_enrichment_result(self, enrich_id: str) -> Optional[Dict[str, Any]]:
        """GET /enrich/{id} — poll enrichment result.

        Returns the full result dict on HTTP 200, or None on HTTP 202 (pending).
        """
        await self._ensure_session()
        url = f"{self.config.base_url}/enrich/{enrich_id}"
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("enrichmentStatus") == "done":
                    return data
                return None  # still processing
            if resp.status == 202:
                return None
            text = await resp.text()
            logger.debug(f"Lemlist poll {enrich_id} returned {resp.status}: {text[:100]}")
            return None

    async def enrich_bulk(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """POST /v2/enrichments/bulk — submit up to 500 enrichments."""
        await self._ensure_session()
        url = f"{self.config.base_url.replace('/api', '')}/v2/enrichments/bulk"
        await lemlist_rate_limiter.wait_for_token()
        async with self.session.post(url, json=items) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            text = await resp.text()
            logger.warning(f"Lemlist bulk enrich {resp.status}: {text[:200]}")
            if resp.status == 400 and "credit" in text.lower():
                self.credit_exhausted = True
            return []

    # ------------------------------------------------------------------
    # Apollo-compatible interface
    # ------------------------------------------------------------------

    async def search_companies_preview(
        self,
        industry: str,
        location: str,
        max_results: int,
        company_size: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """Drop-in replacement for ApolloClient.search_companies_preview().

        Returns list of dicts with keys matching the Apollo preview shape:
        apollo_company_id, company_name, website, industry, location,
        employee_count, revenue_estimate, description.
        """
        registry = await self._get_filters()

        filters = []
        if location:
            filters.extend(registry.build_filters(company_country=[location]))
        if industry:
            # Use keywordInCompany for generic industry terms — LinkedIn's
            # currentCompanySubIndustry requires exact taxonomy values.
            filters.extend(registry.build_filters(keyword_in_company=[industry]))
        if company_size:
            mapped = self._map_company_size(company_size)
            if mapped:
                filters.extend(registry.build_filters(company_size=mapped))
        if keywords:
            filters.extend(registry.build_filters(keyword_in_company=keywords))

        if not filters:
            return []

        data = await self.search_companies(
            filters=filters, page=page, size=min(max_results, 500)
        )
        results = data.get("results", [])
        preview_leads = []
        for c in results:
            try:
                cid = c.get("_id") or c.get("company_id")
                name = c.get("company_name", "")
                if not cid or not name:
                    continue
                preview_leads.append({
                    "apollo_company_id": cid,
                    "company_name": name,
                    "website": c.get("company_website_url") or (
                        f"https://{c['company_domain']}" if c.get("company_domain") else None
                    ),
                    "industry": c.get("company_industry"),
                    "location": self._company_location(c),
                    "employee_count": self._parse_employee_count(c.get("company_employee_count")),
                    "revenue_estimate": c.get("revenue_bucket"),
                    "description": c.get("company_description"),
                })
            except Exception as e:
                logger.debug(f"Error mapping Lemlist company {c.get('company_name')}: {e}")
        return preview_leads

    async def enrich_company_emails(
        self,
        company_ids: List[str],
        companies: Optional[List[Dict[str, Any]]] = None,
        job_titles: Optional[List[str]] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Drop-in replacement for ApolloClient.enrich_company_emails().

        For each company: find decision makers via people DB, enrich best
        candidate's email via async /enrich, return dict in Apollo shape.
        """
        await self._ensure_session()
        enriched_leads: List[Dict[str, Any]] = []
        companies = companies or []
        registry = await self._get_filters()

        for idx, company_id in enumerate(company_ids):
            try:
                meta = companies[idx] if idx < len(companies) else None
                company_name = (meta or {}).get("company_name", "")
                original_company_name = company_name
                website = (meta or {}).get("website", "")
                location = (meta or {}).get("location", "")
                domain = _extract_domain(website)

                # Find decision makers via people DB
                person = await self._find_decision_maker(
                    company_name=company_name,
                    domain=domain,
                    job_titles=job_titles,
                    department=department,
                    seniority_level=seniority_level,
                    registry=registry,
                )

                if not person:
                    logger.warning(f"No decision maker found for {company_name}")
                    continue

                # Extract person details
                full_name = person.get("full_name", "")
                name_parts = full_name.split(None, 1) if full_name else []
                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                title = person.get("title", "")

                # Get company domain from person's experience if we don't have it
                if not domain:
                    exps = person.get("experiences", [])
                    if exps:
                        domain = exps[0].get("company_domain")

                if not first_name or not last_name:
                    logger.debug(f"Skipping enrich — incomplete name: '{full_name}'")
                    continue

                # Enrich email via async /enrich + polling
                poller = self._get_poller()
                result = await poller.enrich_and_wait(
                    first_name=first_name,
                    last_name=last_name,
                    company_name=company_name or None,
                    company_domain=domain,
                )

                email = self._extract_email(result)

                # Get company metadata from person's experience
                exp = (person.get("experiences") or [{}])[0] if person.get("experiences") else {}
                company_industry = exp.get("company_industry") or person.get("lead_industry")
                company_loc = self._person_company_location(person, exp)

                enriched_leads.append({
                    "apollo_company_id": company_id,
                    "company_name": exp.get("company_name") or company_name,
                    "original_company_name": original_company_name,
                    "website": exp.get("company_website_url") or website or (
                        f"https://{domain}" if domain else None
                    ),
                    "industry": company_industry,
                    "location": company_loc or location,
                    "contact_name": full_name,
                    "contact_email": email,
                    "contact_title": title,
                    "apollo_person_id": str(person.get("lead_id", "")),
                    "final_score": _get_title_priority(title),
                })

                if email:
                    logger.info(f"Enriched {company_name}: {full_name} <{email}>")
                else:
                    logger.info(f"Enriched {company_name}: {full_name} (no email)")

                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error enriching company {company_id}: {e}")
                continue

        logger.info(f"Lemlist enrichment: {len(enriched_leads)}/{len(company_ids)} done")

        return enriched_leads

    async def get_saved_contacts_for_company(
        self, company_name: str, company_id: str
    ) -> List[Dict[str, Any]]:
        """Lemlist has no org-wide saved-contacts API. Always returns []."""
        return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _find_decision_maker(
        self,
        company_name: str,
        domain: Optional[str],
        job_titles: Optional[List[str]],
        department: Optional[str],
        seniority_level: Optional[str],
        registry: FilterRegistry,
    ) -> Optional[Dict[str, Any]]:
        """Search Lemlist people DB for the best decision maker at a company.

        Uses ``currentTitle`` filter (not ``seniority``) because Lemlist's
        seniority values are non-standard strings like "Department Leadership"
        that don't map to conventional job levels.
        """
        from database.queries import normalize_company_name

        # Determine title search values
        if job_titles and len(job_titles) > 0:
            title_values = job_titles
        else:
            title_values = [
                "CEO", "CTO", "CMO", "CFO", "COO",
                "President", "VP", "Vice President",
                "Director", "Manager", "Head of",
                "Owner", "Founder", "Co-Founder", "Partner",
            ]

        # Strategy 1: company name + title filter (most precise)
        filters = []
        if company_name:
            filters.extend(registry.build_filters(company_name=[company_name]))
        filters.extend(registry.build_filters(job_title=title_values))
        if department:
            filters.extend(registry.build_filters(department=[department]))

        if filters:
            data = await self.search_people(filters=filters, size=10)
            people = data.get("results", [])
            if people:
                return self._pick_best_person(
                    people, company_name, normalize_company_name
                )

        # Strategy 2: company name only, broader search (no title filter)
        if company_name:
            filters = registry.build_filters(company_name=[company_name])
            if filters:
                data = await self.search_people(filters=filters, size=10)
                people = data.get("results", [])
                if people:
                    return self._pick_best_person(
                        people, company_name, normalize_company_name
                    )

        # Strategy 3: if we have a domain, try website filter
        if domain:
            filters = registry.build_filters(company_website=[f"https://{domain}"])
            if filters:
                data = await self.search_people(filters=filters, size=10)
                people = data.get("results", [])
                if people:
                    return self._pick_best_person(
                        people, company_name, normalize_company_name
                    )

        return None

    def _pick_best_person(
        self,
        people: List[Dict[str, Any]],
        target_company: str,
        normalize_fn,
    ) -> Optional[Dict[str, Any]]:
        """Pick the highest-priority person whose company matches the target."""
        target_norm = normalize_fn(target_company) if target_company else ""

        # Filter to people whose current company matches
        matched = []
        for p in people:
            person_company = p.get("current_exp_company_name", "")
            if not person_company:
                exps = p.get("experiences", [])
                if exps:
                    person_company = exps[0].get("company_name", "")
            if not person_company:
                continue

            person_norm = normalize_fn(person_company)
            # Fuzzy match: normalized names share common prefix or substring
            if target_norm and person_norm:
                if (target_norm in person_norm or person_norm in target_norm
                        or target_norm == person_norm):
                    matched.append(p)
            else:
                matched.append(p)

        if not matched:
            # Fall back to all results if none match company name
            matched = [p for p in people if p.get("full_name")]

        if not matched:
            return None

        # Sort by title priority (descending)
        matched.sort(
            key=lambda p: _get_title_priority(p.get("title", "")),
            reverse=True,
        )
        return matched[0]

    @staticmethod
    def _extract_email(result: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract email from Lemlist enrichment result."""
        if not result:
            return None
        data = result.get("data", {})
        email_data = data.get("email") or data.get("find_email")
        if not email_data:
            return None
        if email_data.get("notFound"):
            return None
        email = email_data.get("email")
        if email and "@" in email:
            return email
        return None

    @staticmethod
    def _company_location(company: Dict[str, Any]) -> Optional[str]:
        """Build location string from a Lemlist company result."""
        city = company.get("company_headquarters_city")
        country = company.get("company_headquarters_country")
        loc = company.get("company_location")
        if city and country:
            return f"{city}, {country}"
        return city or country or loc

    @staticmethod
    def _person_company_location(
        person: Dict[str, Any], exp: Dict[str, Any]
    ) -> Optional[str]:
        city = exp.get("company_headquarters_city")
        country = exp.get("company_headquarters_country")
        if city and country:
            return f"{city}, {country}"
        return person.get("location") or person.get("country")

    @staticmethod
    def _parse_employee_count(val) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, int):
            return val
        try:
            return int(str(val).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _map_company_size(size_str: str) -> List[str]:
        """Map Apollo-style size ranges to Lemlist headcount filter values."""
        mapping = {
            "1-10": ["1-10"],
            "11-50": ["11-50"],
            "51-200": ["51-200"],
            "201-1000": ["201-500", "501-1000"],
            "1000+": ["1001-5000", "5001-10000", "10001+"],
            "1001-5000": ["1001-5000"],
            "5001-10000": ["5001-10000"],
            "10001+": ["10001+"],
        }
        return mapping.get(size_str, [size_str])

    @staticmethod
    def _map_seniority(level: Optional[str]) -> List[str]:
        """Map caller's seniority to Lemlist seniority filter values."""
        if not level:
            return ["Owner", "CXO", "VP", "Director", "Manager"]
        level_lower = level.lower()
        mapping = {
            "c-level": ["CXO"],
            "c_level": ["CXO"],
            "cxo": ["CXO"],
            "vp": ["VP"],
            "director": ["Director"],
            "manager": ["Manager"],
            "owner": ["Owner"],
            "founder": ["Owner"],
            "partner": ["Partner"],
            "senior": ["Senior"],
            "entry": ["Entry"],
        }
        return mapping.get(level_lower, [level])
