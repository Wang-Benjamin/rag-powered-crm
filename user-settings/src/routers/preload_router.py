"""
Preload Router - Handles data preloading for all pages after login
"""
import asyncio
import os
import httpx
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from config import settings
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preload")

# Service URLs - configurable via environment variables for deployed environments
CRM_API = os.getenv("CRM_SERVICE_URL", "http://localhost:8003") + "/api/crm"
LEADGEN_API = os.getenv("LEADGEN_SERVICE_URL", "http://localhost:9000") + "/api"
USER_SETTINGS_API = os.getenv("USER_SETTINGS_URL", "http://localhost:8005") + "/api"

async def fetch_endpoint(client: httpx.AsyncClient, name: str, url: str, headers: dict):
    """Fetch a single endpoint and return progress with data"""
    try:
        response = await client.get(url, headers=headers, timeout=30.0)
        if response.status_code == 200:
            data = response.json() if response.content else None
            return {
                "name": name, 
                "status": "success", 
                "data_size": len(response.content),
                "data": data
            }
        elif response.status_code in [403, 404]:
            # Expected for optional/not-yet-configured endpoints
            logger.info(f"Endpoint {name} not available: {response.status_code}")
            return {"name": name, "status": "skipped", "reason": f"Not configured (HTTP {response.status_code})"}
        else:
            return {"name": name, "status": "error", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.error(f"Error preloading {name}: {e}")
        return {"name": name, "status": "error", "error": str(e)}

@router.get("/all")
async def preload_all_pages(authorization: str = Header(None)):
    """
    Preload data for all major pages.
    Returns a streaming response with progress updates.
    """
    async def generate_progress():
        """Generate progress updates as Server-Sent Events.
        Fetches all endpoints in parallel for faster loading.
        """
        headers = {"Authorization": authorization} if authorization else {}

        # Define all endpoints to preload (only cache what contexts actually use)
        endpoints = [
            # CRM endpoints - cached by CRMContext
            {"name": "crm_customers", "url": f"{CRM_API}/customers"},
            {"name": "crm_deals", "url": f"{CRM_API}/deals"},
            {"name": "crm_employees", "url": f"{CRM_API}/employees"},

            # Lead Gen endpoints - cached by LeadContext
            # Note: Leads endpoint returns all leads, context splits them by source
            {"name": "leads_all", "url": f"{LEADGEN_API}/leads/with-personnel?page=1&per_page=1000"},
        ]

        total = len(endpoints)

        # Send initial progress — all items start loading at once
        initial_progress = {'progress': 20, 'total': total, 'message': 'Loading data...'}
        yield f"data: {json.dumps(initial_progress)}\n\n"

        # Send "loading" status for all endpoints simultaneously
        for endpoint in endpoints:
            loading_update = {
                'progress': 20,
                'total': total,
                'completed': 0,
                'message': f"Loading {endpoint['name'].replace('_', ' ').title()}...",
                'result': {'name': endpoint['name'], 'status': 'loading'}
            }
            yield f"data: {json.dumps(loading_update)}\n\n"

        # Fetch all endpoints in parallel
        results_queue = asyncio.Queue()

        async def fetch_and_enqueue(client, endpoint):
            result = await fetch_endpoint(client, endpoint["name"], endpoint["url"], headers)
            await results_queue.put(result)

        async with httpx.AsyncClient() as client:
            tasks = [asyncio.create_task(fetch_and_enqueue(client, ep)) for ep in endpoints]

            # Stream results as they complete
            completed = 0
            for _ in range(total):
                result = await results_queue.get()
                completed += 1
                progress = 20 + int((completed / total) * 80)

                message = f"Loaded {result['name'].replace('_', ' ').title()}"
                if result.get("status") == "error":
                    message += " (failed)"

                completion_update = {
                    'progress': progress,
                    'total': total,
                    'completed': completed,
                    'message': message,
                    'result': result
                }
                yield f"data: {json.dumps(completion_update)}\n\n"

            # Ensure all tasks are done
            await asyncio.gather(*tasks)

        # Send completion
        final_update = {
            'progress': 100,
            'total': total,
            'completed': total,
            'message': 'Preload complete!',
            'done': True
        }
        yield f"data: {json.dumps(final_update)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@router.get("/status")
async def preload_status():
    """
    Check if preload is available and which services are reachable
    """
    services = {
        "crm": {"url": f"{CRM_API}/health", "reachable": False},
        "leadgen": {"url": f"{LEADGEN_API}/health", "reachable": False},
    }
    
    async with httpx.AsyncClient() as client:
        for service_name, service_info in services.items():
            try:
                response = await client.get(service_info["url"], timeout=5.0)
                service_info["reachable"] = response.status_code == 200
            except:
                pass
    
    return {
        "preload_available": True,
        "services": services
    }
