"""Discover and cache Lemlist filter IDs at runtime."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Hardcoded fallback — used when GET /database/filters fails.
# Discovered from the live API on 2026-04-17.
FALLBACK_FILTER_IDS = {
    "country": "country",
    "industry": "currentCompanySubIndustry",
    "company_size": "currentCompanyHeadcount",
    "seniority": "seniority",
    "job_title": "currentTitle",
    "department": "department",
    "company_name": "currentCompany",
    "company_country": "currentCompanyCountry",
    "company_location": "currentCompanyLocation",
    "company_website": "currentCompanyWebsiteUrl",
    "keyword": "keyword",
    "keyword_in_company": "keywordInCompany",
    "company_market": "currentCompanyMarket",
    "company_type": "currentCompanyType",
    "company_technologies": "currentCompanyTechnologies",
    "company_revenue": "currentCompanyRevenue",
}


class FilterRegistry:
    """Singleton that discovers Lemlist filter IDs via GET /database/filters."""

    _instance: Optional["FilterRegistry"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self):
        self._raw_filters: List[Dict[str, Any]] = []
        self._id_index: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    @classmethod
    async def get_instance(cls, client) -> "FilterRegistry":
        async with cls._lock:
            if cls._instance is None:
                cls._instance = FilterRegistry()
            if not cls._instance._loaded:
                await cls._instance._load(client)
            return cls._instance

    async def _load(self, client) -> None:
        try:
            filters = await client.get_filters()
            self._raw_filters = filters
            self._id_index = {f["filterId"]: f for f in filters}
            self._loaded = True
            logger.info(f"Lemlist filter registry loaded: {len(filters)} filters")
        except Exception as e:
            logger.warning(f"Failed to load Lemlist filters, using fallback: {e}")
            self._loaded = True  # don't retry every call

    def get_filter_id(self, concept: str) -> Optional[str]:
        """Map a logical concept to its Lemlist filterId.

        Tries the live-discovered index first, then falls back to hardcoded IDs.
        """
        # Direct match (caller already knows the filterId)
        if concept in self._id_index:
            return concept
        # Concept mapping
        fid = FALLBACK_FILTER_IDS.get(concept)
        if fid and (fid in self._id_index or not self._id_index):
            return fid
        return None

    def build_filters(self, **kwargs) -> List[Dict[str, Any]]:
        """Build a Lemlist-compatible filters array.

        Example::

            registry.build_filters(
                country=["United States"],
                industry=["Construction"],
            )
        """
        result = []
        for concept, values in kwargs.items():
            if values is None:
                continue
            if not isinstance(values, list):
                values = [values]
            if not values:
                continue
            fid = self.get_filter_id(concept)
            if fid:
                result.append({"filterId": fid, "in": values, "out": []})
            else:
                logger.debug(f"No Lemlist filter for concept '{concept}', skipping")
        return result
