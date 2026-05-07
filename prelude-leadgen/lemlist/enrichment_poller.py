"""Poll Lemlist async enrichment results."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EnrichmentPoller:
    """Submit enrichment requests and poll until results are ready."""

    def __init__(self, client):
        self.client = client

    async def enrich_and_wait(
        self,
        first_name: str,
        last_name: str,
        company_name: Optional[str] = None,
        company_domain: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        max_wait_seconds: float = 30.0,
        max_polls: int = 15,
    ) -> Optional[Dict[str, Any]]:
        """Submit a single enrichment and poll until complete.

        Returns the enrichment result dict, or None on timeout / failure.
        The ``email`` key is at ``result["data"]["email"]["email"]`` when found.
        """
        try:
            enrich_id = await self.client.enrich_person(
                first_name=first_name,
                last_name=last_name,
                company_name=company_name,
                company_domain=company_domain,
                linkedin_url=linkedin_url,
                find_email=True,
            )
        except Exception as e:
            logger.warning(f"Lemlist enrich submit failed for {first_name} {last_name}: {e}")
            return None

        if not enrich_id:
            return None

        start = time.monotonic()
        interval = 1.0
        for poll in range(1, max_polls + 1):
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            if elapsed > max_wait_seconds:
                logger.warning(f"Lemlist enrich timeout ({elapsed:.1f}s) for {enrich_id}")
                return None

            try:
                result = await self.client.get_enrichment_result(enrich_id)
            except Exception as e:
                logger.debug(f"Lemlist poll error for {enrich_id}: {e}")
                result = None

            if result is not None:
                logger.debug(f"Lemlist enrich done in {elapsed:.1f}s (poll {poll})")
                return result

            # Backoff: 1s, 2s, 3s, 4s, 5s, 5s, ...
            interval = min(interval + 1.0, 5.0)

        logger.warning(f"Lemlist enrich exhausted {max_polls} polls for {enrich_id}")
        return None

    async def enrich_batch_and_wait(
        self,
        items: List[Dict[str, Any]],
        max_wait_seconds: float = 60.0,
    ) -> List[Optional[Dict[str, Any]]]:
        """Submit a batch via /v2/enrichments/bulk and poll each result.

        Each item in *items* must have ``first_name``, ``last_name``, and
        optionally ``company_name``, ``company_domain``.  Returns a list
        of results aligned with *items* (None for failures).
        """
        bulk_input = []
        for idx, item in enumerate(items):
            entry: Dict[str, Any] = {
                "input": {
                    "firstName": item.get("first_name", ""),
                    "lastName": item.get("last_name", ""),
                },
                "enrichmentRequests": ["find_email"],
                "metadata": {"index": idx},
            }
            if item.get("company_name"):
                entry["input"]["companyName"] = item["company_name"]
            if item.get("company_domain"):
                entry["input"]["companyDomain"] = item["company_domain"]
            bulk_input.append(entry)

        try:
            bulk_response = await self.client.enrich_bulk(bulk_input)
        except Exception as e:
            logger.warning(f"Lemlist bulk enrich failed: {e}")
            return [None] * len(items)

        # Map each successful submission to its enrichment ID
        id_map: Dict[int, str] = {}
        for resp_item in bulk_response:
            meta = resp_item.get("metadata", {})
            idx = meta.get("index")
            enrich_id = resp_item.get("id")
            if idx is not None and enrich_id:
                id_map[idx] = enrich_id

        # Poll all enrichment IDs concurrently
        sem = asyncio.Semaphore(4)

        async def _poll_one(enrich_id: str) -> Optional[Dict[str, Any]]:
            async with sem:
                start = time.monotonic()
                interval = 1.0
                for _ in range(15):
                    await asyncio.sleep(interval)
                    if time.monotonic() - start > max_wait_seconds:
                        return None
                    try:
                        result = await self.client.get_enrichment_result(enrich_id)
                        if result is not None:
                            return result
                    except Exception:
                        pass
                    interval = min(interval + 1.0, 5.0)
                return None

        tasks = {}
        for idx, eid in id_map.items():
            tasks[idx] = asyncio.create_task(_poll_one(eid))

        results: List[Optional[Dict[str, Any]]] = [None] * len(items)
        for idx, task in tasks.items():
            results[idx] = await task
        return results
