"""
ImportYeti API Client

Wrapper around the ImportYeti REST API for trade data queries.
Base URL: https://data.importyeti.com/v1.0
Auth: IYApiKey header
Date format: mm/dd/yyyy (US format, NOT ISO)

Verified credit costs (March 2026):
  - FREE: /supplier/search, /database-updated
  - 0.1/result: /powerquery/*, /product/*/companies, /product/*/suppliers
  - 1 credit: /company/{company}, /supplier/{supplier}, /bol/{number}
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional, List, Dict, Any

import httpx

from config.services import ExternalServices
from utils.rate_limiter import get_rate_limiter, ExponentialBackoff
from importyeti.domain.schemas import (
    PowerQueryCompaniesResponse,
    CompanyDetailResponse,
    DatabaseUpdatedResponse,
    PowerQueryCompany,
    ParsedBolCompany,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://data.importyeti.com/v1.0"
AUTH_HEADER = "IYApiKey"
DEFAULT_TIMEOUT = 30.0

# Rate limiting: 10 concurrent requests, 30 requests/min
_semaphore = asyncio.Semaphore(10)
_rate_limiter = get_rate_limiter("importyeti_api", rate_limit=30, time_period=60)
_backoff = ExponentialBackoff(base_delay=1, max_delay=30, jitter=True)


# ── Fixture mode (tests) ─────────────────────────────────────────────
# When IMPORTYETI_FIXTURE_DIR is set, the four paid endpoints below read
# local JSON instead of the network. Missing fixtures raise FileNotFoundError
# — never fall through to the network. Used only by the integration test
# harness to avoid ImportYeti credit burn.

def _fixture_dir() -> Optional[str]:
    return os.environ.get("IMPORTYETI_FIXTURE_DIR")


def _load_json_fixture(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _assert_inside_dir(candidate: str, base: str) -> None:
    """Guard against path traversal via untrusted slug/hs_code values.

    `os.path.join` happily accepts `../../etc/foo`; `os.path.realpath`
    canonicalizes the result so we can verify it still sits under the
    fixture root. Defense-in-depth — the fixture gate is only active
    when tests set IMPORTYETI_FIXTURE_DIR, but a malformed slug should
    never escape the sandbox.
    """
    real_base = os.path.realpath(base)
    real_candidate = os.path.realpath(candidate)
    if not (
        real_candidate == real_base
        or real_candidate.startswith(real_base + os.sep)
    ):
        raise ValueError(
            f"Fixture path {candidate!r} resolves outside {base!r}"
        )


def _resolve_buyer_pq_fixture(hs_code: str) -> Optional[str]:
    dir_ = _fixture_dir()
    if not dir_:
        return None
    candidates = [
        os.path.join(dir_, f"powerquery_buyers_{hs_code}.json"),
        os.path.join(dir_, "powerquery_sample_raw.json"),
    ]
    for path in candidates:
        _assert_inside_dir(path, dir_)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"IMPORTYETI_FIXTURE_DIR set ({dir_}) but no buyer PowerQuery fixture for "
        f"hs_code={hs_code} (tried {candidates})"
    )


def _resolve_supplier_pq_fixture(hs_code: str) -> Optional[str]:
    dir_ = _fixture_dir()
    if not dir_:
        return None
    candidates = [
        os.path.join(dir_, f"powerquery_suppliers_{hs_code}.json"),
        os.path.join(dir_, "competitors_raw.json"),
    ]
    for path in candidates:
        _assert_inside_dir(path, dir_)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"IMPORTYETI_FIXTURE_DIR set ({dir_}) but no supplier PowerQuery fixture for "
        f"hs_code={hs_code} (tried {candidates})"
    )


def _resolve_company_detail_fixture(slug: str) -> Optional[str]:
    dir_ = _fixture_dir()
    if not dir_:
        return None
    path = os.path.join(dir_, f"deep_enrich_{slug}.json")
    _assert_inside_dir(path, dir_)
    if os.path.exists(path):
        return path
    raise FileNotFoundError(
        f"IMPORTYETI_FIXTURE_DIR set ({dir_}) but no deep_enrich_{slug}.json"
    )


def _resolve_supplier_detail_fixture(slug: str) -> Optional[str]:
    dir_ = _fixture_dir()
    if not dir_:
        return None
    path = os.path.join(dir_, f"competitor_enrich_{slug}.json")
    _assert_inside_dir(path, dir_)
    if os.path.exists(path):
        return path
    raise FileNotFoundError(
        f"IMPORTYETI_FIXTURE_DIR set ({dir_}) but no competitor_enrich_{slug}.json"
    )


def _wrap_powerquery_response(raw: Any) -> Dict[str, Any]:
    """powerquery_sample_raw.json is a bare list of PowerQueryCompany dicts.
    Shape it into PowerQueryCompaniesResponse: {"data": {"totalCompanies": N, "data": [...]}}.
    Already-wrapped fixtures pass through unchanged.
    """
    if isinstance(raw, list):
        return {
            "requestCost": 0.0,
            "data": {"totalCompanies": len(raw), "data": raw},
        }
    return raw


def _wrap_company_detail(raw: Any) -> Dict[str, Any]:
    """deep_enrich_*.json is a flat dict of enrichment fields.
    Wrap into CompanyDetailResponse: {"data": {...}}. A fixture that
    already has the response envelope (nested `data` dict alongside
    `requestCost`) passes through unchanged — detected structurally
    rather than by key-set superset so an enrichment dict that merely
    happens to contain a `data` field isn't mis-detected.
    """
    if (
        isinstance(raw, dict)
        and isinstance(raw.get("data"), dict)
        and "requestCost" in raw
    ):
        return raw
    return {"requestCost": 0.0, "data": raw}


class ImportYetiClient:
    """HTTP client for the ImportYeti Data API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ExternalServices.IMPORTYETI_API_KEY
        if not self.api_key:
            logger.warning("IMPORTYETI_API_KEY not set — API calls will fail")

    def _headers(self) -> Dict[str, str]:
        return {AUTH_HEADER: self.api_key}

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request with rate limiting and retry.
        Uses semaphore for concurrency control + token bucket for rate limiting.
        """
        url = f"{BASE_URL}{path}"

        for attempt in range(max_retries + 1):
            async with _semaphore:
                await _rate_limiter.wait_for_token()

                start_ms = int(time.time() * 1000)
                try:
                    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                        response = await client.request(
                            method=method,
                            url=url,
                            params=params,
                            headers=self._headers(),
                        )

                    duration_ms = int(time.time() * 1000) - start_ms

                    if response.status_code == 429:
                        logger.warning(
                            f"ImportYeti rate limited (429) on {path}, attempt {attempt + 1}"
                        )
                        if attempt < max_retries:
                            await _backoff.sleep(attempt)
                            continue
                        response.raise_for_status()

                    response.raise_for_status()
                    data = response.json()

                    logger.debug(
                        f"ImportYeti {method} {path}: {response.status_code} "
                        f"({duration_ms}ms, cost={data.get('requestCost', '?')})"
                    )
                    return data

                except httpx.TimeoutException:
                    logger.warning(f"ImportYeti timeout on {path}, attempt {attempt + 1}")
                    if attempt < max_retries:
                        await _backoff.sleep(attempt)
                        continue
                    raise
                except httpx.HTTPStatusError:
                    raise
                except Exception as e:
                    logger.error(f"ImportYeti request error on {path}: {e}")
                    if attempt < max_retries:
                        await _backoff.sleep(attempt)
                        continue
                    raise

        raise RuntimeError(f"ImportYeti request to {path} failed after {max_retries + 1} attempts")

    # === Utility (FREE) ===

    async def check_database_updated(self) -> DatabaseUpdatedResponse:
        """
        GET /v1.0/database-updated
        Cost: FREE
        Returns the last database update date.
        """
        data = await self._request("GET", "/database-updated")
        return DatabaseUpdatedResponse(**data)

    # === Primary Search (0.1 credits per result) ===

    async def power_query_buyers(
        self,
        hs_code: Optional[str] = None,
        product_description: Optional[str] = None,
        start_date: str = "01/01/2019",
        end_date: Optional[str] = None,
        page_size: int = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        supplier_country: Optional[str] = None,
        company_total_shipments: Optional[str] = None,
    ) -> PowerQueryCompaniesResponse:
        """
        GET /v1.0/powerquery/us-import/companies
        Cost: 0.1 credits per result

        Search for US importers by HS code, product description, or both.
        The ImportYeti endpoint supports both params simultaneously — supplying
        both narrows results to records matching the HS code AND the keyword.

        hs_code: HS code string. Supports wildcards (9405*) and boolean
            operators (AND, OR, NOT). Optional when product_description is given.
        product_description: Free-text product keyword search. Optional when
            hs_code is given. At least one of hs_code or product_description
            must be provided.

        supplier_country="china" filters for buyers importing FROM China.
        company_total_shipments accepts a PowerQuery range string like
        "20 TO 300" — used by the two-pager shift-left filter to exclude
        freight forwarders (high count) and noise (low count) at the API
        layer rather than post-filtering.
        """
        if not hs_code and not product_description:
            raise ValueError("power_query_buyers requires at least one of hs_code or product_description")

        if hs_code:
            fixture_path = _resolve_buyer_pq_fixture(hs_code)
            if fixture_path:
                logger.info("[fixture] power_query_buyers hs_code=%s from %s", hs_code, fixture_path)
                raw = _load_json_fixture(fixture_path)
                return PowerQueryCompaniesResponse(**_wrap_powerquery_response(raw))

        params: Dict[str, Any] = {
            "start_date": start_date,
            "page_size": min(page_size, 100),
            "offset": offset,
        }
        if hs_code:
            params["hs_code"] = hs_code
        if product_description:
            params["product_description"] = product_description
        if end_date:
            params["end_date"] = end_date
        if sort_by:
            params["sort_by"] = sort_by
        if supplier_country:
            params["supplier_country"] = supplier_country
        if company_total_shipments:
            params["company_total_shipments"] = company_total_shipments

        data = await self._request("GET", "/powerquery/us-import/companies", params=params)
        return PowerQueryCompaniesResponse(**data)

    async def power_query_suppliers(
        self,
        hs_code: str,
        start_date: str = "01/01/2019",
        end_date: Optional[str] = None,
        page_size: int = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        supplier_country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GET /v1.0/powerquery/us-import/suppliers
        Cost: 0.1 credits per result

        Search overseas suppliers aggregated from US import bills of lading.
        Used for live CN supplier totals on the one-pager.
        """
        fixture_path = _resolve_supplier_pq_fixture(hs_code)
        if fixture_path:
            logger.info("[fixture] power_query_suppliers hs_code=%s from %s", hs_code, fixture_path)
            raw = _load_json_fixture(fixture_path)
            # supplier PowerQuery returns raw dict; mirror the shape loosely.
            if isinstance(raw, list):
                return {"data": {"totalSuppliers": len(raw), "data": raw}, "requestCost": 0.0}
            return raw

        params: Dict[str, Any] = {
            "hs_code": hs_code,
            "start_date": start_date,
            "page_size": min(page_size, 100),
            "offset": offset,
        }
        if end_date:
            params["end_date"] = end_date
        if sort_by:
            params["sort_by"] = sort_by
        if supplier_country:
            params["supplier_country"] = supplier_country

        return await self._request("GET", "/powerquery/us-import/suppliers", params=params)

    # === Deep Enrichment (Tier 3 — 1 credit) ===

    async def get_company_detail(self, company_slug: str) -> CompanyDetailResponse:
        """
        GET /v1.0/company/{company}
        Cost: 1 credit flat

        Returns comprehensive data: suppliers_table, time_series,
        recent_bols, other_addresses_contact_info, etc.
        """
        fixture_path = _resolve_company_detail_fixture(company_slug)
        if fixture_path:
            logger.info("[fixture] get_company_detail slug=%s from %s", company_slug, fixture_path)
            raw = _load_json_fixture(fixture_path)
            return CompanyDetailResponse(**_wrap_company_detail(raw))

        data = await self._request("GET", f"/company/{company_slug}")
        return CompanyDetailResponse(**data)

    # === Supplier Detail (1 credit) ===

    async def get_supplier_detail(self, supplier_slug: str) -> Dict[str, Any]:
        """
        GET /v1.0/supplier/{supplier}
        Cost: 1 credit flat

        Returns comprehensive supplier data: time_series, companies_table,
        products, ports, etc. Used for competitor lazy-enrichment.
        """
        fixture_path = _resolve_supplier_detail_fixture(supplier_slug)
        if fixture_path:
            logger.info("[fixture] get_supplier_detail slug=%s from %s", supplier_slug, fixture_path)
            raw = _load_json_fixture(fixture_path)
            if isinstance(raw, dict) and "data" in raw and set(raw.keys()) <= {
                "data", "requestCost", "creditsRemaining", "executionTime",
            }:
                return raw
            return {"requestCost": 0.0, "data": raw}

        data = await self._request("GET", f"/supplier/{supplier_slug}")
        return data

    # === Helpers ===

    @staticmethod
    def extract_slug(company_link: str) -> str:
        """Extract slug from company_link. '/company/ikea-supply' -> 'ikea-supply'."""
        if not company_link:
            return ""
        return company_link.rstrip("/").split("/")[-1]

    @staticmethod
    def parse_address(address_list: Optional[List[Dict[str, Any]]]) -> tuple:
        """
        Parse address from PowerQuery company_address list.
        Returns (full_address, city, state).

        Handles both comma-separated ("123 Main St, City, IL 60077")
        and space-separated ("123 Main St City Il 60077 Us") formats.
        """
        if not address_list:
            return None, None, None

        if isinstance(address_list[0], dict):
            addr = address_list[0].get("key", "")
        else:
            addr = str(address_list[0])

        if not addr:
            return None, None, None

        import re
        city = None
        state = None

        # Try to find "ST ZIP" or "ST ZIP US" pattern near end of string
        # Matches: "Il 60077", "Ca 91746 Us", "NY 10001"
        m = re.search(r'\b([A-Za-z]{2})\s+(\d{5})\b', addr)
        if m:
            state = m.group(1).upper()
            # City: text between last street suffix and state code
            before = addr[:m.start()].strip().rstrip(',').strip()
            # Split after common street suffixes/numbers to isolate city
            city_match = re.search(
                r'(?:Ave|St|Rd|Dr|Drive|Blvd|Ln|Way|Ct|Pl|Pkwy|Parkway|Hwy|Suite|Ste|Unit|Fl|Box \d+)\s+(.+?)$',
                before, flags=re.IGNORECASE
            )
            if city_match:
                city = city_match.group(1).strip().title()
            else:
                # Comma-separated fallback
                comma_parts = [p.strip() for p in before.split(",")]
                if len(comma_parts) >= 2:
                    city = comma_parts[-1].title()

        return addr, city, state

    def parse_powerquery_company(
        self, company: PowerQueryCompany, hs_code: str
    ) -> ParsedBolCompany:
        """Convert a PowerQuery company result to a ParsedBolCompany for cache storage."""
        slug = self.extract_slug(company.company_link or "")
        address, city, state = self.parse_address(
            [kc.model_dump() for kc in company.company_address] if company.company_address else None
        )

        website = None
        if company.company_website:
            website = company.company_website[0].key

        shipping_ports = [p.key for p in (company.shipping_port or [])]
        ports_of_entry = [p.key for p in (company.port_of_entry or [])]
        product_descs = [p.key for p in (company.product_description or [])]
        hs_codes_list = [h.key for h in (company.hs_code or [])]
        if not hs_codes_list and hs_code:
            hs_codes_list = [hs_code]

        return ParsedBolCompany(
            importyeti_slug=slug,
            company_name=company.key,
            company_total_shipments=company.total_shipments,
            address=address,
            city=city,
            state=state,
            website=website,
            shipping_ports=shipping_ports or None,
            ports_of_entry=ports_of_entry or None,
            product_descriptions=product_descs or None,
            hs_codes=hs_codes_list or None,
            matching_shipments=company.doc_count,
            weight_kg=company.weight,
            teu=company.teu,
        )
