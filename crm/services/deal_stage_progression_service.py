# DEPRECATED: Stage progression replaced by event-driven room_status updates. See docs/pivot/13_DEAL_ROOM_IMPLEMENTATION_PLAN.md
#!/usr/bin/env python3
"""
Deal Stage Progression Service
Analyzes all active deals and updates stages based on AI analysis of communications.

Uses existing infrastructure:
- get_comprehensive_customer_data() for data fetching
- TenantPoolManager for database access
- DealStageProgressionAgent for AI analysis
"""

import sys
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.queries.deal_queries import (
    get_active_deals_for_room_analysis as get_active_deals_for_stage_analysis,
    get_deal_communications_comprehensive,
    update_deal_room_status as update_deal_stage,
    update_deal_timestamp
)
from agents.deals.deal_stage_progression_agent import DealStageProgressionAgent
from service_core.db import get_pool_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def process_single_deal(
    deal: Dict[str, Any],
    agent: DealStageProgressionAgent,
    days_lookback: int,
    dry_run: bool,
    db_name: str
) -> Dict[str, Any]:
    """
    Process a single deal for stage progression analysis.

    Args:
        deal: Deal dictionary
        agent: DealStageProgressionAgent instance
        days_lookback: Days to look back for communications
        dry_run: If True, don't update database
        db_name: Database name for pool_manager

    Returns:
        Result dictionary with status and details
    """
    deal_id = deal['deal_id']
    client_id = deal['client_id']
    current_stage = deal['stage']

    try:
        logger.info(f"Analyzing deal {deal_id}: {deal['deal_name']} (Current: {current_stage})")

        # Create authenticated_user context for data fetching
        authenticated_user = {
            'email': deal.get('employee_email', 'system@prelude.com'),
            'employee_id': deal.get('employee_id')
        }

        # Fetch communications using existing comprehensive data function
        communications = await get_deal_communications_comprehensive(
            client_id,
            authenticated_user,
            days_lookback
        )

        emails = communications.get('emails', [])
        notes = communications.get('notes', [])

        if not emails and not notes:
            logger.info(f"  No recent communications found for deal {deal_id}, skipping")
            return {
                "deal_id": deal_id,
                "status": "skipped",
                "reason": "no_communications"
            }

        logger.info(f"  Found {len(emails)} emails and {len(notes)} notes")

        # Prepare agent input
        agent_input = {
            "deal_id": deal_id,
            "deal_name": deal['deal_name'],
            "current_stage": current_stage,
            "client_id": client_id,
            "employee_id": deal['employee_id'],
            "emails": emails,
            "notes": notes,
            "deal_metadata": {
                "value_usd": float(deal['value_usd']) if deal['value_usd'] else 0.0,
                "expected_close_date": str(deal['expected_close_date']) if deal['expected_close_date'] else None,
                "last_contact_date": str(deal['last_contact_date']) if deal['last_contact_date'] else None
            }
        }

        # Analyze with agent (acquire conn for preferences lookup + DB updates)
        async with get_pool_manager().acquire(db_name) as conn:
            result = await agent.analyze_deal_stage_progression(agent_input, conn=conn)

            # Log recommendation
            logger.info(f"  Recommendation: {current_stage} -> {result['recommended_stage']}")
            logger.info(f"  Should Update: {result['should_update']} (Confidence: {result['confidence']})")
            logger.info(f"  Reasoning: {result['reasoning'][:200]}...")

            # Always update timestamp for tracking purposes, even if stage doesn't change
            if not dry_run:
                if result['should_update']:
                    # Stage is changing - use update_deal_stage
                    success = await update_deal_stage(
                        conn,
                        deal_id,
                        result['recommended_stage'],
                        result['reasoning'],
                        updated_by="automated_stage_progression",
                        update_type="automatic"
                    )

                    if success:
                        logger.info(f"  Updated deal {deal_id} stage to {result['recommended_stage']}")
                        return {
                            "deal_id": deal_id,
                            "status": "updated",
                            "old_stage": current_stage,
                            "new_stage": result['recommended_stage'],
                            "confidence": result['confidence']
                        }
                    else:
                        logger.error(f"  Failed to update deal {deal_id}")
                        return {
                            "deal_id": deal_id,
                            "status": "error",
                            "reason": "update_failed"
                        }
                else:
                    # Stage is not changing - update timestamp only to track the refresh
                    success = await update_deal_timestamp(
                        conn,
                        deal_id,
                        result['reasoning'],
                        updated_by="automated_stage_progression",
                        update_type="automatic"
                    )

                    if success:
                        logger.info(f"  Refreshed deal {deal_id} timestamp (stage unchanged: {current_stage})")
                        return {
                            "deal_id": deal_id,
                            "status": "refreshed",
                            "current_stage": current_stage,
                            "confidence": result['confidence']
                        }
                    else:
                        logger.error(f"  Failed to refresh deal {deal_id} timestamp")
                        return {
                            "deal_id": deal_id,
                            "status": "error",
                            "reason": "timestamp_update_failed"
                        }
            else:
                # Dry run mode
                if result['should_update']:
                    logger.info(f"  [DRY RUN] Would update deal {deal_id} to {result['recommended_stage']}")
                    return {
                        "deal_id": deal_id,
                        "status": "dry_run_update",
                        "old_stage": current_stage,
                        "new_stage": result['recommended_stage'],
                        "confidence": result['confidence']
                    }
                else:
                    logger.info(f"  [DRY RUN] Would refresh deal {deal_id} timestamp (stage unchanged)")
                    return {
                        "deal_id": deal_id,
                        "status": "dry_run_refresh",
                        "current_stage": current_stage,
                        "confidence": result['confidence']
                    }

    except Exception as e:
        logger.error(f"  Error processing deal {deal_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "deal_id": deal_id,
            "status": "error",
            "reason": str(e)
        }


async def process_deal_stage_progression(
    db_name: str,
    batch_size: int = 10,
    days_lookback: int = 30,
    dry_run: bool = False,
    user_email: str = None
):
    """
    Main function to process deal stage progression.

    Args:
        db_name: Database name for pool_manager
        batch_size: Number of deals to process in each batch
        days_lookback: Number of days to look back for communications
        dry_run: If True, only log recommendations without updating database
        user_email: User email for database routing (optional)
    """
    logger.info("=" * 80)
    logger.info("DEAL STAGE PROGRESSION - DAILY RUN")
    logger.info(f"Started at: {datetime.now(timezone.utc)}")
    logger.info(f"Configuration: batch_size={batch_size}, days_lookback={days_lookback}, dry_run={dry_run}")
    logger.info("=" * 80)

    # Initialize agent with OpenAI (faster and more reliable)
    agent = DealStageProgressionAgent(provider="openai", model_name="gpt-4.1-mini", email=user_email)

    # Statistics
    stats = {
        "total_deals": 0,
        "deals_analyzed": 0,
        "stages_updated": 0,
        "timestamps_refreshed": 0,
        "errors": 0,
        "skipped": 0
    }

    try:
        # Fetch active deals
        async with get_pool_manager().acquire(db_name) as conn:
            active_deals = await get_active_deals_for_stage_analysis(conn)
        stats["total_deals"] = len(active_deals)

        logger.info(f"Found {stats['total_deals']} active deals to analyze")

        # Process deals in batches
        for i in range(0, len(active_deals), batch_size):
            batch = active_deals[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: deals {i+1} to {min(i+batch_size, len(active_deals))}")

            # Process batch concurrently
            tasks = [
                process_single_deal(deal, agent, days_lookback, dry_run, db_name)
                for deal in batch
            ]
            results = await asyncio.gather(*tasks)

            # Update statistics
            for result in results:
                stats["deals_analyzed"] += 1

                if result["status"] == "updated":
                    stats["stages_updated"] += 1
                elif result["status"] == "refreshed":
                    stats["timestamps_refreshed"] += 1
                elif result["status"] == "skipped":
                    stats["skipped"] += 1
                elif result["status"] == "error":
                    stats["errors"] += 1

            # Small delay between batches to avoid overwhelming the system
            if i + batch_size < len(active_deals):
                await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Database error in deal stage progression for {user_email}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        stats["errors"] += 1

    # Log final statistics
    logger.info("=" * 80)
    logger.info("DEAL STAGE PROGRESSION - COMPLETED")
    logger.info(f"Finished at: {datetime.now(timezone.utc)}")
    logger.info(f"Statistics:")
    logger.info(f"  Total Deals: {stats['total_deals']}")
    logger.info(f"  Deals Analyzed: {stats['deals_analyzed']}")
    logger.info(f"  Stages Updated: {stats['stages_updated']}")
    logger.info(f"  Timestamps Refreshed (no stage change): {stats['timestamps_refreshed']}")
    logger.info(f"  Skipped (no communications): {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("=" * 80)

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run deal stage progression analysis")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--days-lookback", type=int, default=30, help="Days to look back for communications")
    parser.add_argument("--dry-run", action="store_true", help="Run without updating database")
    parser.add_argument("--user-email", type=str, default=None, help="User email for database routing")
    parser.add_argument("--db-name", type=str, required=True, help="Database name for pool_manager")

    args = parser.parse_args()

    asyncio.run(process_deal_stage_progression(
        db_name=args.db_name,
        batch_size=args.batch_size,
        days_lookback=args.days_lookback,
        dry_run=args.dry_run,
        user_email=args.user_email
    ))
