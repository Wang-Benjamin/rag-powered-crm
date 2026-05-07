"""
Internal BoL Client — HTTP client to the internal leads DB service (port 8007)
for BoL cache operations.

Follows the same fire-and-forget pattern as internal_leads_client.py:
- Non-blocking: errors are logged but don't fail the caller
- JWT auth forwarding via Authorization header
- httpx.AsyncClient with timeout

After migration 009a:
  - search_cache / search_competitor_cache accept optional `products` list
  - cache-state endpoints removed
  - save_to_cache / save_competitors_to_cache no longer send cache_states, and
    no longer assert on search_results_upserted (per-HS metrics now live on
    the parent row as hs_metrics JSONB, not a separate counter).
"""

import os
import logging
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)

INTERNAL_LEADS_SERVICE_URL = os.getenv(
    "INTERNAL_LEADS_SERVICE_URL", "http://localhost:8007"
)
BOL_PREFIX = "/api/internal-leads/bol"
BOL_COMPETITOR_PREFIX = "/api/internal-leads/bol-competitors"

# Shared AsyncClient with connection pooling.
_LIMITS = httpx.Limits(
    max_connections=50,
    max_keepalive_connections=20,
    keepalive_expiry=60.0,
)
_client: httpx.AsyncClient = httpx.AsyncClient(limits=_LIMITS)


def _get_client() -> httpx.AsyncClient:
    return _client


async def close_client() -> None:
    """Close the shared AsyncClient. Call from FastAPI lifespan shutdown."""
    global _client
    if not _client.is_closed:
        await _client.aclose()
    _client = httpx.AsyncClient(limits=_LIMITS)


async def search_cache(
    hs_codes: Optional[List[str]] = None,
    products: Optional[List[str]] = None,
    max_results: int = 500,
    auth_token: str = "",
    min_score: Optional[int] = None,
    *,
    slim: bool,
) -> Optional[List[Dict[str, Any]]]:
    """Search BoL cache for companies by HS code(s), product description(s), or both.

    GET /bol/search?hs_codes=940540&products=wooden+furniture&max_results=500

    slim=True drops heavy JSONB fields (recent_bols, time_series, supplier_breakdown).
    Returns list of cached companies or None on error.
    """
    if not hs_codes and not products:
        logger.warning("search_cache: at least one of hs_codes or products is required")
        return None

    try:
        params: Dict[str, Any] = {"max_results": max_results}
        if hs_codes:
            params["hs_codes"] = ",".join(hs_codes)
        if products:
            params["products"] = ",".join(products)
        if min_score is not None:
            params["min_score"] = min_score
        if slim:
            params["slim"] = "true"

        response = await _get_client().get(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/search",
            params=params,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=180.0,
        )

        if response.status_code == 200:
            result = response.json()
            companies = result.get("companies", [])
            logger.info(
                f"BoL cache search: {len(companies)} companies found "
                f"for hs_codes={hs_codes} products={products} (total_cached={result.get('total_cached', 0)})"
            )
            return companies
        else:
            logger.warning(
                f"BoL cache search failed: {response.status_code} - {response.text}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning(f"BoL cache search timeout for hs_codes={hs_codes} products={products}")
        return None
    except httpx.ConnectError:
        logger.debug(
            f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL} (non-blocking)"
        )
        return None
    except Exception as e:
        logger.warning(f"BoL cache search error (non-blocking): {e}")
        return None


async def save_to_cache(
    companies: List[Dict[str, Any]],
    search_results: List[Dict[str, Any]],
    auth_token: str = "",
) -> bool:
    """Batch upsert companies and per-HS metrics to BoL cache.

    After migration 009a the server folds search_results entries into
    bol_companies.hs_metrics JSONB. We no longer assert on a separate
    search_results_upserted counter — just the parent `companies_upserted`.
    """
    try:
        request_body = {
            "companies": companies,
            "search_results": search_results,
        }

        response = await _get_client().post(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/cache",
            json=request_body,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=180.0,
        )

        if response.status_code == 200:
            result = response.json()
            companies_upserted = result.get("companies_upserted", 0)
            expected_companies = len(companies)
            logger.info(
                f"BoL cache save: {companies_upserted}/{expected_companies} companies"
            )
            if companies_upserted != expected_companies:
                logger.warning(
                    "BoL cache save incomplete: expected %s, got %s",
                    expected_companies, companies_upserted,
                )
                return False
            return True
        else:
            logger.warning(
                f"BoL cache save failed: {response.status_code} - {response.text}"
            )
            return False

    except httpx.TimeoutException:
        logger.warning(f"BoL cache save timeout (companies={len(companies)})")
        return False
    except httpx.ConnectError:
        logger.debug(
            f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL} (non-blocking)"
        )
        return False
    except Exception as e:
        logger.warning(f"BoL cache save error (non-blocking): {e}")
        return False


async def update_enrichment(
    slug: str,
    data: Dict[str, Any],
    auth_token: str = "",
) -> bool:
    """Update enrichment data for a cached BoL company."""
    try:
        response = await _get_client().post(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/enrich/{slug}",
            json=data,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=15.0,
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(
                f"BoL enrichment update for {slug}: "
                f"status={result.get('enrichment_status', 'unknown')}"
            )
            return True
        elif response.status_code == 404:
            logger.warning(f"BoL company not found for enrichment: {slug}")
            return False
        else:
            logger.warning(
                f"BoL enrichment update failed for {slug}: "
                f"{response.status_code} - {response.text}"
            )
            return False

    except httpx.TimeoutException:
        logger.warning(f"BoL enrichment update timeout for {slug}")
        return False
    except httpx.ConnectError as e:
        logger.error(
            f"Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}"
        )
        return False
    except Exception as e:
        logger.warning(f"BoL enrichment update error for {slug} (non-blocking): {e}")
        return False


async def get_company(
    slug: str,
    auth_token: str = "",
) -> Optional[Dict[str, Any]]:
    """Get a single BoL company by slug."""
    try:
        response = await _get_client().get(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/company/{slug}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30.0,
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            logger.warning(
                f"BoL company fetch failed for {slug}: "
                f"{response.status_code} - {response.text}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning(f"BoL company fetch timeout for {slug}")
        return None
    except httpx.ConnectError as e:
        logger.error(
            f"Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}"
        )
        return None
    except Exception as e:
        logger.warning(f"BoL company fetch error for {slug} (non-blocking): {e}")
        return None


async def fetch_company_by_slug(
    slug: str,
    auth_token: str = "",
) -> Optional[Dict[str, Any]]:
    """Hydrate a single BoL company's full payload (incl. heavy JSONB).

    Used by the two-pager slim-first fetch path: cache search runs slim,
    then top-30 buyers are hydrated in parallel via this endpoint.
    Timeout 25s — the underlying internal-leads handler does a single
    psycopg2 fetch (~1-2s warm), but the first batch under concurrent
    load hits cold pool connections that can take 10-15s. A failed
    hydrate just falls back to the live IY deep_enrich path, so a
    too-tight cap here trades cached data for IY API spend.
    """
    try:
        response = await _get_client().get(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/company/{slug}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=25.0,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return None
        logger.warning(
            f"BoL company hydrate failed for {slug}: "
            f"{response.status_code} - {response.text}"
        )
        return None
    except httpx.TimeoutException:
        logger.warning(f"BoL company hydrate timeout for {slug}")
        return None
    except httpx.ConnectError:
        logger.debug(
            f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL} (non-blocking)"
        )
        return None
    except Exception as e:
        logger.warning(f"BoL company hydrate error for {slug} (non-blocking): {e}")
        return None


async def log_api_call(
    endpoint: str,
    method: str = "GET",
    status_code: Optional[int] = None,
    credits_used: float = 0,
    result_count: Optional[int] = None,
    hs_code: Optional[str] = None,
    user_email: Optional[str] = None,
    request_params: Optional[Dict[str, Any]] = None,
    response_summary: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    auth_token: str = "",
) -> bool:
    """Log an ImportYeti API call for credit tracking."""
    try:
        request_body = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "credits_used": credits_used,
            "result_count": result_count,
            "hs_code": hs_code,
            "user_email": user_email,
            "request_params": request_params,
            "response_summary": response_summary,
            "error_message": error_message,
            "duration_ms": duration_ms,
        }

        response = await _get_client().post(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_PREFIX}/api-log",
            json=request_body,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30.0,
        )

        if response.status_code == 200:
            return True
        else:
            logger.debug(
                f"API log failed: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        logger.debug(f"API log error (non-blocking): {e}")
        return False


# ── Competitor Cache Methods ──────────────────────────────────────────────────


async def search_competitor_cache(
    hs_codes: Optional[List[str]] = None,
    products: Optional[List[str]] = None,
    max_results: int = 500,
    auth_token: str = "",
) -> Optional[List[Dict[str, Any]]]:
    """Search competitor cache by HS code(s), product description(s), or both.

    GET {BOL_COMPETITOR_PREFIX}/search?hs_codes=...&products=...&max_results=...
    """
    if not hs_codes and not products:
        logger.warning("search_competitor_cache: at least one of hs_codes or products is required")
        return None

    try:
        params: Dict[str, Any] = {"max_results": max_results}
        if hs_codes:
            params["hs_codes"] = ",".join(hs_codes)
        if products:
            params["products"] = ",".join(products)

        response = await _get_client().get(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_COMPETITOR_PREFIX}/search",
            params=params,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=60.0,
        )

        if response.status_code == 200:
            result = response.json()
            competitors = result.get("competitors", [])
            logger.info(
                f"Competitor cache search: {len(competitors)} competitors found "
                f"for hs_codes={hs_codes} products={products} (total_cached={result.get('total_cached', 0)})"
            )
            return competitors
        else:
            logger.warning(
                f"Competitor cache search failed: {response.status_code} - {response.text}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning(f"Competitor cache search timeout for hs_codes={hs_codes} products={products}")
        return None
    except httpx.ConnectError:
        logger.debug(
            f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL} (non-blocking)"
        )
        return None
    except Exception as e:
        logger.warning(f"Competitor cache search error (non-blocking): {e}")
        return None


async def save_competitors_to_cache(
    competitors: List[Dict[str, Any]],
    search_results: List[Dict[str, Any]],
    auth_token: str = "",
) -> bool:
    """Batch upsert competitors with per-HS metrics to the competitor cache.

    Per migration 009a, server folds search_results into
    bol_competitor_companies.hs_metrics JSONB. No longer assert on
    search_results_upserted counter.
    """
    try:
        request_body = {
            "competitors": competitors,
            "search_results": search_results,
        }

        response = await _get_client().post(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_COMPETITOR_PREFIX}/cache",
            json=request_body,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=60.0,
        )

        if response.status_code == 200:
            result = response.json()
            competitors_upserted = result.get("competitors_upserted", 0)
            expected_competitors = len(competitors)
            logger.info(
                f"Competitor cache save: {competitors_upserted}/{expected_competitors} competitors"
            )
            if competitors_upserted != expected_competitors:
                logger.warning(
                    "Competitor cache save incomplete: expected %s, got %s",
                    expected_competitors, competitors_upserted,
                )
                return False
            return True
        else:
            logger.warning(
                f"Competitor cache save failed: {response.status_code} - {response.text}"
            )
            return False

    except httpx.TimeoutException:
        logger.warning(f"Competitor cache save timeout (competitors={len(competitors)})")
        return False
    except httpx.ConnectError:
        logger.debug(
            f"Internal leads DB service unavailable at {INTERNAL_LEADS_SERVICE_URL} (non-blocking)"
        )
        return False
    except Exception as e:
        logger.warning(f"Competitor cache save error (non-blocking): {e}")
        return False


async def update_competitor_enrichment(
    slug: str,
    data: Dict[str, Any],
    auth_token: str = "",
) -> bool:
    """Update enrichment data for a cached competitor."""
    try:
        response = await _get_client().post(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_COMPETITOR_PREFIX}/enrich/{slug}",
            json=data,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=15.0,
        )

        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            logger.warning(f"Competitor not found for enrichment: {slug}")
            return False
        else:
            logger.warning(
                f"Competitor enrichment update failed for {slug}: "
                f"{response.status_code} - {response.text}"
            )
            return False

    except httpx.TimeoutException:
        logger.warning(f"Competitor enrichment update timeout for {slug}")
        return False
    except httpx.ConnectError as e:
        logger.error(
            f"Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}"
        )
        return False
    except Exception as e:
        logger.warning(f"Competitor enrichment update error for {slug} (non-blocking): {e}")
        return False


async def get_competitor(
    slug: str,
    auth_token: str = "",
) -> Optional[Dict[str, Any]]:
    """Get a single cached competitor by slug."""
    try:
        response = await _get_client().get(
            f"{INTERNAL_LEADS_SERVICE_URL}{BOL_COMPETITOR_PREFIX}/company/{slug}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=30.0,
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            logger.warning(
                f"Competitor fetch failed for {slug}: "
                f"{response.status_code} - {response.text}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning(f"Competitor fetch timeout for {slug}")
        return None
    except httpx.ConnectError as e:
        logger.error(
            f"Cannot connect to internal leads DB service at {INTERNAL_LEADS_SERVICE_URL}: {e}"
        )
        return None
    except Exception as e:
        logger.warning(f"Competitor fetch error for {slug} (non-blocking): {e}")
        return None
