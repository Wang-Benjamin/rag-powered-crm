import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import json
import asyncpg

# Import tenant connection dependency
from service_core.db import get_tenant_connection, get_pool_manager

# Import service functions
from services.interaction_service import (
    get_recent_customer_interactions,
    get_interaction_summary_options
)
from services.cache_service import clear_cache

# Import models
from models.crm_models import InteractionSummaryRequest, InteractionSummaryResponse

# Import CRM endpoint for customer data
from routers.crm_data_router import get_customer_by_id_endpoint as get_customer_crm

# Direct imports of agent classes
from agents.insights.icebreaker_intro_agent import IcebreakerIntroAgent
from agents.insights.next_action_insight_agent import NextActionInsightAgent
from agents.insights.restart_momentum_insight_agent import RestartMomentumInsightAgent
from agents.insights.deal_retrospective_agent import DealRetrospectiveAgent

# Import centralized database queries
from data.queries.insights_queries import (
    analyze_customer_activity,
    get_comprehensive_customer_data,
    get_customer_basic_info,
    get_recent_interactions_summary
)

# Import cached summary service
from services.cached_summary_service import cached_summary_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple agent registry with direct imports
AGENT_REGISTRY = {
    "IcebreakerIntroAgent": IcebreakerIntroAgent,
    "NextActionInsightAgent": NextActionInsightAgent,
    "RestartMomentumInsightAgent": RestartMomentumInsightAgent,
    "DealRetrospectiveAgent": DealRetrospectiveAgent
}

logger.info(f"Initialized agent registry with {len(AGENT_REGISTRY)} agents: {list(AGENT_REGISTRY.keys())}")


def select_agent_for_customer(customer_analysis: Dict[str, Any]) -> str:
    """
    Select the appropriate agent based on customer engagement across all channels.

    Uses total engagement (interactions + emails + notes) rather than just
    deals/interactions, so customers with active email threads but no formal
    deal record still get actionable insights.

    Decision matrix:
        | Engagement       | Has active deals | No active deals (but has closed) | No deals at all  |
        |------------------|------------------|---------------------------------|------------------|
        | Moderate+ (3+)   | NextAction       | NextAction                       | NextAction       |
        | Low (1-2)        | RestartMomentum  | DealRetrospective                | Icebreaker       |
        | None (0)         | RestartMomentum  | DealRetrospective                | Icebreaker       |
    """
    total_engagement = customer_analysis.get("total_engagement", 0)
    recent_engagement = customer_analysis.get("recent_engagement", 0)
    has_active_deals = customer_analysis.get("has_active_deals", False)
    deal_count = customer_analysis.get("deal_count", 0)

    # Moderate+ engagement (3+ total signals across any channel) → NextAction
    # regardless of deal status — enough history to analyze and recommend next steps
    if total_engagement >= 3:
        selected = "NextActionInsightAgent"

    # Has active deals but low/no engagement → RestartMomentum
    elif has_active_deals:
        selected = "RestartMomentumInsightAgent"

    # Has closed deals but no active ones and low engagement → Retrospective
    elif deal_count > 0:
        selected = "DealRetrospectiveAgent"

    # Truly blank slate — no deals, minimal communication → Icebreaker
    else:
        selected = "IcebreakerIntroAgent"

    logger.info(
        f"Agent selection: {selected} "
        f"(engagement={total_engagement}, recent_14d={recent_engagement}, "
        f"deals={deal_count}, active_deals={int(has_active_deals)})"
    )
    return selected

# DEBUG TEST ENDPOINT WITHOUT AUTH
@router.post("/debug/customers/{customer_id}/interaction-summary/generate")
async def debug_generate_interaction_summary(
    customer_id: str,
    request: InteractionSummaryRequest = InteractionSummaryRequest()
) -> InteractionSummaryResponse:
    """Debug version of generate_interaction_summary without authentication"""
    logger.info(f"DEBUG: Starting debug interaction summary for customer {customer_id}")

    # Use fake authenticated user for testing
    authenticated_user = {
        'email': 'debug@test.com',
        'name': 'Debug User',
        'role': 'admin'
    }

    # Call the main logic (no conn available in debug mode)
    return await _generate_interaction_summary_logic(customer_id, request, authenticated_user, conn=None)

@router.get("/cached-summaries/batch")
async def get_cached_summaries_batch(
    request: Request,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Get all cached summaries in a single batch query for CRM initialization.
    Returns zh-CN translations when X-User-Locale header starts with 'zh'.
    """
    conn, user = tenant
    try:
        locale = request.headers.get("X-User-Locale", "en")

        # Get the most recent successful summary per customer
        query = """
        SELECT DISTINCT ON (customer_id)
            customer_id,
            summary_data,
            summary_data_zh,
            generated_at,
            generation_type,
            period_analyzed_days,
            interactions_analyzed,
            agent_used,
            ai_model_used,
            processing_time_ms
        FROM interaction_summaries
        WHERE status = 'success'
        ORDER BY
            customer_id,
            generated_at DESC
        """

        results = await conn.fetch(query)

        use_zh = locale.startswith('zh')

        # Convert to list of summary objects
        summaries = []
        for row in results:
            raw = row['summary_data']
            summary_data = json.loads(raw) if isinstance(raw, str) else raw

            # Serve zh-CN translation when available and locale matches
            if use_zh and row['summary_data_zh']:
                raw_zh = row['summary_data_zh']
                zh_data = json.loads(raw_zh) if isinstance(raw_zh, str) else raw_zh
                summary_data = zh_data

            summaries.append({
                'customer_id': row['customer_id'],
                'summary_data': summary_data,
                'generated_at': row['generated_at'].isoformat() if hasattr(row['generated_at'], 'isoformat') else str(row['generated_at']),
                'generation_type': row['generation_type'],
                'period_analyzed_days': row['period_analyzed_days'],
                'interactions_analyzed': row['interactions_analyzed'],
                'agent_used': row['agent_used'],
                'ai_model_used': row['ai_model_used'],
                'processing_time_ms': row['processing_time_ms']
            })

        logger.info(f"Batch loaded {len(summaries)} cached summaries")
        return summaries

    except Exception as e:
        logger.error(f"Error loading cached summaries batch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load cached summaries: {str(e)}")

@router.get("/customers/{customer_id}/interaction-summary")
async def get_interaction_summary(
    request: Request,
    customer_id: str,
    days_back: int = 30,
    force_refresh: bool = False,
    tenant: tuple = Depends(get_tenant_connection)
) -> InteractionSummaryResponse:
    """
    Get interaction summary for a customer (uses cached summaries when available).
    Returns zh-CN translation when X-User-Locale header starts with 'zh'.
    """
    conn, user = tenant
    try:
        customer_id_int = int(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    locale = request.headers.get("X-User-Locale", "en")
    return await cached_summary_service.get_summary(
        customer_id_int,
        user,
        conn,
        days_back,
        force_refresh,
        locale=locale,
    )

@router.post("/customers/{customer_id}/interaction-summary/generate")
async def generate_interaction_summary(
    customer_id: str,
    request: InteractionSummaryRequest = InteractionSummaryRequest(),
    tenant: tuple = Depends(get_tenant_connection)
) -> InteractionSummaryResponse:
    """
    Generate interaction summary for a customer (always real-time, bypasses cache).
    This endpoint is kept for backward compatibility and manual generation.
    """
    conn, user = tenant
    return await _generate_interaction_summary_logic(customer_id, request, user, conn=conn)

async def _generate_interaction_summary_logic(
    customer_id: str,
    request: InteractionSummaryRequest,
    authenticated_user: dict,
    conn: Optional[asyncpg.Connection] = None
) -> InteractionSummaryResponse:
    """Generate a comprehensive interaction summary for a customer using AI."""

    # If no connection provided, acquire one from pool manager
    if conn is None:
        user_email = authenticated_user.get('email', '')
        db_name = authenticated_user.get('db_name')
        if not db_name:
            db_name = await get_pool_manager().lookup_db_name(user_email)
        async with get_pool_manager().acquire(db_name) as acquired_conn:
            return await _generate_interaction_summary_logic(
                customer_id, request, authenticated_user, conn=acquired_conn
            )

    try:
        logger.info(f"Generating interaction summary for customer {customer_id} (last {request.days_back} days)")

        # Convert customer_id to int for CRM service
        try:
            customer_id_int = int(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")

        # Get customer data using comprehensive CRM service function
        try:
            customer = await get_customer_crm(customer_id_int, (conn, authenticated_user))
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Customer with ID {customer_id} not found")
            raise e

        # Extract user information and get employee_id
        user_name = authenticated_user.get('name', 'Customer Success Manager')
        user_email = authenticated_user.get('email', '')
        user_role = 'Customer Success Manager'  # Default role

        # Get employee information by email
        employee_id = None
        if user_email and conn:
            try:
                row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
                employee_id = row["employee_id"] if row else None
                # Get employee details for proper signature
                emp_row = await conn.fetchrow("SELECT employee_id, name, role, department FROM employee_info WHERE email = $1 LIMIT 1", user_email)
                if emp_row:
                    user_name = emp_row.get('name', user_name)
                    user_role = emp_row.get('role', user_role)
            except Exception as e:
                logger.warning(f"Employee not found for email {user_email}, using all interactions: {e}")

        # Get recent interactions from database - now returns ALL interactions for the customer
        days_back = request.days_back or 30  # Handle None case
        interactions = await get_recent_customer_interactions(customer_id, conn, days_back)

        # NOTE: Don't return early for no interactions - agents can still provide valuable insights!
        # Especially IcebreakerIntroAgent which is designed for customers with little recent activity
        logger.info(f"DEBUG: Found {len(interactions)} interactions for customer {customer_id_int}")

        if not interactions:
            logger.info(f"DEBUG: No recent interactions found, but proceeding with agent-based approach for icebreaker insights")

        # DYNAMIC AGENT SELECTION SYSTEM
        # Analyze customer activity patterns
        logger.info(f"DEBUG: Starting customer analysis for customer {customer_id_int}")
        customer_analysis = await analyze_customer_activity(conn, customer_id_int)
        logger.info(f"DEBUG: Customer recent statistics: {customer_analysis}")

        # Select appropriate agent based on customer patterns
        selected_agent_name = select_agent_for_customer(customer_analysis)
        logger.info(f"DEBUG: Selected agent: {selected_agent_name}")

        # Try agent-based approach first
        summary_data = None
        actual_agent_used = None
        actual_model_used = None

        if selected_agent_name and selected_agent_name in AGENT_REGISTRY:
            try:

                # Initialize the selected agent (agents handle their own initialization)
                agent_class = AGENT_REGISTRY[selected_agent_name]
                logger.info(f"Initializing agent {selected_agent_name} with email={user_email}")
                agent = agent_class(email=user_email)
                logger.info(f"Agent {selected_agent_name} initialized successfully")

                # Capture actual agent and model information
                actual_agent_used = selected_agent_name
                try:
                    # Get model information from the agent's model factory
                    model_info = agent.model_factory.get_model_info()
                    actual_model_used = f"{model_info.provider}-{model_info.model_name}"
                    logger.info(f"DEBUG: Captured model info - Provider: {model_info.provider}, Model: {model_info.model_name}")
                except Exception as model_error:
                    logger.warning(f"Could not capture model info from agent: {model_error}")
                    actual_model_used = "unknown"

                # Get comprehensive customer data via RAG-enhanced retrieval (with fallback)
                logger.info(f"Getting RAG-enhanced customer data")
                try:
                    from data.queries.rag_queries import get_rag_enhanced_customer_data
                    comprehensive_data = await get_rag_enhanced_customer_data(
                        customer_id_int, authenticated_user, agent_type=selected_agent_name, conn=conn)
                    logger.info(f"RAG-enhanced data retrieved: {comprehensive_data is not None}")
                except Exception as rag_err:
                    logger.warning(f"RAG-enhanced retrieval failed, falling back to standard: {rag_err}")
                    comprehensive_data = await get_comprehensive_customer_data(conn, customer_id_int)
                    logger.info(f"Comprehensive data retrieved: {comprehensive_data is not None}")

                if comprehensive_data:
                    # Use comprehensive data structure for agent
                    client_history = comprehensive_data
                    logger.info(f"Using comprehensive data: {len(client_history.get('interaction_details', []))} interactions, "
                               f"{len(client_history.get('deals', []))} deals")
                else:
                    # Fallback to basic data structure if comprehensive data fails
                    logger.warning("Comprehensive data gathering failed, using basic data structure")
                    # Derive primary contact info from personnel list
                    _primary = next((p for p in (customer.personnel or []) if p.isPrimary), None)
                    client_history = {
                        "client_info": {
                            "name": customer.company,
                            "status": customer.status,
                            "primary_contact": _primary.fullName if _primary else "",
                            "email": _primary.email if _primary else "",
                        },
                        "client_details": {
                            "health_score": customer.healthScore or 75,
                            "last_interaction": customer.lastInteraction,
                        },
                        "interaction_details": interactions,
                        "deals": [],
                        "summary_metrics": {
                            "total_interactions": len(interactions),
                            "total_interaction_time_minutes": sum(
                                interaction.get('duration_minutes', 30) for interaction in interactions
                            )
                        }
                    }

                # Generate insights using the selected agent
                logger.info(f" Client history keys: {list(client_history.keys()) if client_history else 'None'}")
                agent_response = await agent.generate_quick_insights(conn, client_history)
                logger.info(f"Agent response received, type: {type(agent_response)}, length: {len(str(agent_response)) if agent_response else 0}")

                # Parse agent response (should be JSON)
                if isinstance(agent_response, str):
                    logger.info(f"Agent response is string, attempting to parse JSON")
                    try:
                        # Strip markdown code blocks if present (fix for IcebreakerIntroAgent)
                        cleaned_response = agent_response.strip()
                        if cleaned_response.startswith('```json'):
                            cleaned_response = cleaned_response.replace('```json', '').replace('```', '')
                        elif cleaned_response.startswith('```'):
                            cleaned_response = cleaned_response.replace('```', '')
                        cleaned_response = cleaned_response.strip()

                        # Fix JSON control character issues - replace literal newlines in string values
                        import re
                        # Simple approach: replace problematic newlines that break JSON parsing
                        # Look for patterns like: "text\nmore text" and convert to "text\\nmore text"
                        cleaned_response = re.sub(r'([^\\])\n([^}\]",\s])', r'\1\\n\2', cleaned_response)
                        # Also handle newlines at the start of continuation lines
                        cleaned_response = re.sub(r'\n(Reasoning:)', r'\\n\1', cleaned_response)
                        agent_data = json.loads(cleaned_response)

                        # Convert agent format to expected API format
                        # Special handling for IcebreakerIntroAgent (new customer scenarios)
                        if selected_agent_name == "IcebreakerIntroAgent":
                            # Format next steps with reasoning on separate lines
                            formatted_next_steps = []
                            for step in agent_data.get('Next Move', [])[:2]:
                                if isinstance(step, str) and "Reasoning:" in step:
                                    # Split action and reasoning
                                    parts = step.split("Reasoning:", 1)
                                    if len(parts) == 2:
                                        action = parts[0].replace("Action:", "").strip()
                                        reasoning = parts[1].strip()
                                        formatted_next_steps.append(f"{action}\n    -> {reasoning}")
                                    else:
                                        formatted_next_steps.append(step)
                                else:
                                    formatted_next_steps.append(step)

                            # Process insights - preserve original order from agent
                            insights = agent_data.get('Insights', [])

                            # Take all insights in the order provided by the agent (up to 3)
                            # Expected order: Experience, Context, Icebreaker
                            final_insights = insights[:3]

                            logger.info(f"ICEBREAKER: Processing {len(insights)} insights from agent")
                            logger.info(f"ICEBREAKER: Final insights in order: {[insight[:50] + '...' for insight in final_insights]}")

                            summary_data = {
                                "summary": "AI Agent Analysis: new customer",
                                "interaction_count": len(interactions),  # Use actual interaction count
                                "recent_activities": final_insights,  # Prioritized AI Insights with icebreakers first
                                "engagement_level": "new",  # Set to "new" for IcebreakerIntroAgent
                                "next_steps": formatted_next_steps,
                            }

                            logger.info(f"ICEBREAKER: Formatted response for new customer with {len(formatted_next_steps)} next steps")
                        else:
                            # Standard format for other agents
                            # Special handling for NextActionInsightAgent - should always be "active"
                            if selected_agent_name == "NextActionInsightAgent":
                                engagement_level = "active"  # NextActionInsightAgent is only used for active customers
                            else:
                                engagement_level = agent_data.get('Activities', 'medium').lower()

                            summary_data = {
                                "summary": f"AI Agent Analysis: {agent_data.get('Activities', 'active')} customer status",
                                "interaction_count": len(interactions),
                                "recent_activities": agent_data.get('Insights', [])[:3],  # Take top 3 insights
                                "engagement_level": engagement_level,
                                "next_steps": agent_data.get('Next Move', [])[:3],  # Take up to 3 recommendations
                            }

                        logger.info(f"AGENT: Successfully generated agent-based summary for customer {customer_id}")

                    except json.JSONDecodeError as e:
                        logger.error(f"DEBUG: JSON parsing failed: {e}")
                        logger.error(f"DEBUG: Raw agent response: {agent_response}")
                        logger.warning(f"AGENT: Agent response not valid JSON, falling back to legacy system: {e}")
                        logger.warning(f"AGENT: Raw response preview: {agent_response[:200]}...")
                        summary_data = None
                else:
                    logger.error(f"DEBUG: Agent response is not a string: {type(agent_response)}")
                    summary_data = None

            except Exception as e:
                logger.error(f"Exception in agent-based analysis: {e}", exc_info=True)
                logger.error(f"Agent {selected_agent_name} failed for customer {customer_id_int}")
                summary_data = None
        else:
            logger.warning(f"DEBUG: Agent not selected or not in registry. Selected: {selected_agent_name}, In registry: {selected_agent_name in AGENT_REGISTRY if selected_agent_name else False}")

        # If agent-based approach failed, raise clear error
        if summary_data is None:
            error_msg = f"Agent-based summary generation failed for customer {customer_id}"
            if selected_agent_name:
                error_msg += f" using {selected_agent_name}"

            logger.error(f"{error_msg}. No fallback system available.")
            logger.error(f"Customer: {customer.company} (ID: {customer_id_int})")
            logger.error(f"Interactions found: {len(interactions)}")

            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate interaction summary. Agent: {selected_agent_name or 'None'}. Please check server logs for details."
            )

        logger.info(f"Successfully generated interaction summary for customer {customer_id}")

        # Determine customer status based on which agent was selected and update database
        customer_status = None

        try:
            logger.info(f"STATUS: Determining customer status for customer {customer_id_int}")

            # SIMPLIFIED LOGIC: Map agent directly to status
            # - NextActionInsightAgent -> active (recent interactions + active deals)
            # - RestartMomentumInsightAgent -> inactive (no recent interactions but has active deals)
            # - IcebreakerIntroAgent -> active (new customer, treat as active opportunity)
            # - DealRetrospectiveAgent -> completed (has interactions but no active deals - completed engagement cycle)

            if actual_agent_used == 'NextActionInsightAgent':
                customer_status = 'active'
            elif actual_agent_used == 'RestartMomentumInsightAgent':
                customer_status = 'inactive'
            elif actual_agent_used == 'IcebreakerIntroAgent':
                customer_status = 'active'  # New customers are active opportunities
            elif actual_agent_used == 'DealRetrospectiveAgent':
                customer_status = 'completed'  # Has interactions but no active deals - completed engagement cycle
            else:
                # Fallback for legacy system or unknown agents
                engagement_level = summary_data.get('engagement_level', '') if summary_data else ''
                if engagement_level in ['churned', 'lost']:
                    customer_status = 'lost'
                elif engagement_level in ['inactive', 'low']:
                    customer_status = 'inactive'
                else:
                    customer_status = 'active'

            logger.info(f"STATUS: Customer {customer_id_int} - Status: '{customer_status}' (Agent: '{actual_agent_used}')")

            # Update database with customer status
            if customer_status and conn:
                try:
                    logger.info(f"UPDATE: Updating customer {customer_id_int} - status='{customer_status}'")

                    update_query = """
                        UPDATE clients
                        SET status = $1, updated_at = $2
                        WHERE client_id = $3
                    """
                    await conn.execute(update_query, customer_status, datetime.now(timezone.utc), customer_id_int)

                    logger.info(f"UPDATE: Successfully committed updates for customer {customer_id_int} - status='{customer_status}'")

                    # Clear cache for this customer
                    clear_cache("get_all_customers")
                    clear_cache("get_dashboard_stats")
                    clear_cache(f"get_customer_by_id:{customer_id_int}")

                except Exception as db_error:
                    logger.error(f"UPDATE: Failed to update database: {db_error}")
                    # Don't fail the entire request if DB update fails

        except Exception as status_error:
            logger.error(f"STATUS: Customer status calculation/update failed: {status_error}")
            # Don't fail the entire request if status update fails

        return InteractionSummaryResponse(
            status="success",
            summary_data=summary_data,
            customer_id=customer_id_int,
            customer_name=customer.company,
            interactions_analyzed=len(interactions),
            period_analyzed=f"{days_back} days",
            generated_at=datetime.now(timezone.utc).isoformat(),
            agent_used=actual_agent_used,
            ai_model_used=actual_model_used,
        )

    except Exception as e:
        logger.error(f"Error generating interaction summary for customer {customer_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate interaction summary: {str(e)}"
        )

# Administrative endpoints for automated summary system
@router.get("/admin/summary-cache/stats")
async def get_summary_cache_stats(
    tenant: tuple = Depends(get_tenant_connection)
):
    """Get cache statistics for monitoring."""
    conn, user = tenant

    stats = await cached_summary_service.get_cache_stats(conn)
    return {"status": "success", "cache_stats": stats}

@router.post("/admin/summary-batch/run")
async def trigger_batch_summary_generation(
    test_mode: bool = False,
    max_customers: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Manually trigger batch summary generation."""
    conn, user = tenant

    from services.interaction_summary_scheduler import summary_scheduler

    db_name = user.get('db_name', '')
    result = await summary_scheduler.force_run_now(db_name, test_mode, max_customers)
    return result

@router.delete("/admin/summary-cache/clear")
async def clear_summary_cache(
    customer_id: Optional[int] = None,
    older_than_days: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Clear cached summaries."""
    conn, user = tenant

    deleted_count = await cached_summary_service.clear_cache(conn, customer_id, older_than_days)
    return {"status": "success", "deleted_count": deleted_count}

@router.get("/admin/summary-batch/status")
async def get_batch_status(
    tenant: tuple = Depends(get_tenant_connection)
):
    """Get batch job status and monitoring information."""
    conn, user = tenant

    from services.interaction_summary_scheduler import summary_scheduler

    db_name = user.get('db_name', '')
    batch_status = await summary_scheduler.get_batch_status(db_name)
    return {"status": "success", "batch_status": batch_status}

@router.post("/admin/generate-customer-summary/{customer_id}")
async def generate_customer_summary_with_cleanup(
    customer_id: str,
    request: InteractionSummaryRequest = InteractionSummaryRequest(),
    clear_old: bool = True,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Generate summary for a specific customer with selective cleanup."""
    conn, user = tenant

    try:
        customer_id_int = int(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    from services.interaction_summary_scheduler import summary_scheduler

    result = await summary_scheduler.generate_single_customer_summary(
        customer_id_int,
        user,
        request.days_back,
        clear_old=clear_old
    )

    if result["status"] == "success":
        return result["summary_response"]
    else:
        raise HTTPException(status_code=500, detail=result["message"])

@router.get("/customers/{customer_id}/interaction-summary-options")
async def get_interaction_summary_options_endpoint(
    customer_id: str,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Get available options for interaction summary generation"""
    conn, user = tenant

    try:
        customer_id_int = int(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    # Extract user information and get employee_id
    user_email = user.get('email', '')

    # Get employee information by email
    employee_id = None
    if user_email:
        try:
            row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
            employee_id = row["employee_id"] if row else None
        except Exception as e:
            logger.warning(f"Employee not found for email {user_email}, using all interactions: {e}")

    # Get interaction summary options - filtered by employee if available
    if employee_id is not None:
        return await get_interaction_summary_options(customer_id, conn, employee_id)
    else:
        return await get_interaction_summary_options(customer_id, conn)
