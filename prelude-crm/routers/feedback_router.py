"""
Feedback Router - Handles all feedback-related endpoints for CRM
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from service_core.db import get_tenant_connection
from models.crm_models import FeedbackCreate, FeedbackUpdate, FeedbackResponse, paginated_response
from data.repositories.feedback_repository import FeedbackRepository
from data.repositories.user_preferences_repository import UserPreferencesRepository
from agents.feedback.feedback_agent import FeedbackAnalysisAgent
from agents.feedback.category_preference_agent import CategoryPreferenceAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize repositories and agents
feedback_repo = FeedbackRepository()
user_prefs_repo = UserPreferencesRepository()
feedback_agent = FeedbackAnalysisAgent()
category_pref_agent = CategoryPreferenceAgent()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def check_feedback_ownership(conn, feedback_id: int, employee_id: int) -> bool:
    """
    Check if the feedback belongs to the employee.

    Args:
        conn: asyncpg connection
        feedback_id: Feedback ID
        employee_id: Employee ID

    Returns:
        True if employee owns the feedback, False otherwise
    """
    row = await conn.fetchrow(
        "SELECT employee_id FROM crm_feedback WHERE feedback_id = $1",
        feedback_id
    )
    if not row:
        return False
    return row['employee_id'] == employee_id


async def is_admin(conn, user_email: str) -> bool:
    """
    Check if user has admin role.

    Args:
        conn: asyncpg connection
        user_email: User email

    Returns:
        True if user is admin, False otherwise
    """
    row = await conn.fetchrow("SELECT access FROM employee_info WHERE email = $1 LIMIT 1", user_email)
    role = row["access"] if row else None
    return role == 'admin' if role else False


# ============================================================================
# FEEDBACK ENDPOINTS
# ============================================================================

@router.post("/feedback", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Create new feedback for a customer or deal.

    - **customer_id**: ID of the customer
    - **deal_id**: Optional deal ID (for deal-specific feedback)
    - **feedback_category**: Category of feedback ('churn_risk', 'ai_insights', 'stage_progression', 'deal_insights')
    - **rating**: Rating from 1 to 5 stars
    - **feedback_text**: Optional text feedback
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        entity_desc = f"deal {feedback_data.deal_id}" if feedback_data.deal_id else f"customer {feedback_data.customer_id}"
        logger.info(f"Creating feedback for {entity_desc} category {feedback_data.feedback_category} by {user_email}")
        logger.info(f"Feedback data: customer_id={feedback_data.customer_id}, deal_id={feedback_data.deal_id}, category={feedback_data.feedback_category}, rating={feedback_data.rating}")

        # Pydantic validators handle feedback_category and rating validation

        # Get employee ID
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check if user already has feedback for this customer/deal and category
        existing_feedback = await feedback_repo.get_user_feedback(
            conn,
            feedback_data.customer_id,
            employee_id,
            feedback_data.feedback_category,
            feedback_data.deal_id
        )

        if existing_feedback:
            # Automatically update existing feedback (append to feedback_history)
            logger.info(f"Found existing feedback (ID: {existing_feedback['feedback_id']}), updating with new entry")
            result = await feedback_repo.update_feedback(
                conn=conn,
                feedback_id=existing_feedback['feedback_id'],
                employee_id=employee_id,
                rating=feedback_data.rating,
                feedback_text=feedback_data.feedback_text
            )
            if not result:
                raise HTTPException(status_code=500, detail="Failed to update feedback")
        else:
            # Create new feedback
            logger.info(f"No existing feedback found, creating new entry")
            result = await feedback_repo.create_feedback(
                conn=conn,
                customer_id=feedback_data.customer_id,
                employee_id=employee_id,
                feedback_category=feedback_data.feedback_category,
                rating=feedback_data.rating,
                feedback_text=feedback_data.feedback_text,
                deal_id=feedback_data.deal_id
            )
            if not result:
                raise HTTPException(status_code=500, detail="Failed to create feedback")

        # Generate AI summary
        logger.info(f"Generating AI summary for feedback {result['feedback_id']}")
        ai_summary = feedback_agent.analyze_feedback_history(
            feedback_history=result.get('feedback_history', []),
            current_rating=result['rating'],
            feedback_category=result['feedback_category'],
            customer_id=result['customer_id'],
            deal_id=result.get('deal_id')
        )

        # Update database with AI summary
        if ai_summary:
            await feedback_repo.update_ai_summary(
                conn=conn,
                feedback_id=result['feedback_id'],
                ai_summary=ai_summary
            )
            result['ai_summary'] = ai_summary
            logger.info(f"✅ AI summary generated and saved for feedback {result['feedback_id']}")
        else:
            logger.warning(f"⚠️ No AI summary generated for feedback {result['feedback_id']}")
            result['ai_summary'] = None

        # Update category preferences (non-blocking)
        logger.info(f"📊 Updating category preferences for {user_email}, category: {result['feedback_category']}")
        try:
            # Get existing preferences for this category
            category_prefs = await user_prefs_repo.get_category_preferences(conn, user_email, result['feedback_category'])

            # Extract new preferences using agent
            extracted = category_pref_agent.extract_preferences_from_feedback(
                feedback_text=feedback_data.feedback_text or "",
                rating=result['rating'],
                category=result['feedback_category'],
                existing_preferences=category_prefs
            )

            # Merge if existing preferences found
            if category_prefs:
                feedback_count = category_prefs.get('feedback_count', 0)
                rating_delta = abs(result['rating'] - category_prefs.get('last_rating', result['rating']))

                merged = category_pref_agent.merge_preferences(category_prefs, extracted, feedback_count, rating_delta)
                merged['feedback_count'] = feedback_count + 1
                merged['last_rating'] = result['rating']
            else:
                # First feedback for this category
                merged = extracted
                merged['feedback_count'] = 1
                merged['last_rating'] = result['rating']

            # Update in database
            update_result = await user_prefs_repo.update_category_preference(
                conn=conn,
                email=user_email,
                category=result['feedback_category'],
                preferences=merged
            )

            if update_result and update_result.get('success'):
                logger.info(f"✅ Category preferences updated successfully")
            else:
                logger.warning(f"⚠️ Category preference update failed")

        except Exception as e:
            # Non-blocking: don't fail feedback submission if preference update fails
            logger.error(f"❌ Error updating category preferences: {e}", exc_info=True)

        return FeedbackResponse(
            feedback_id=result['feedback_id'],
            customer_id=result['customer_id'],
            deal_id=result.get('deal_id'),
            feedback_category=result['feedback_category'],
            employee_id=result['employee_id'],
            rating=result['rating'],
            feedback_history=result.get('feedback_history', []),
            ai_summary=result.get('ai_summary'),
            created_at=result['created_at'].isoformat() if result['created_at'] else None,
            updated_at=result['updated_at'].isoformat() if result['updated_at'] else None
        )

    except HTTPException as he:
        logger.warning(f"HTTP Exception creating feedback: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Error creating feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/customers/{customer_id}/feedback")
async def get_feedback_by_customer(
    customer_id: int,
    category: Optional[str] = None,
    deal_id: Optional[int] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Get all feedback for a specific customer or deal, optionally filtered by category.

    - Admins can see all feedback
    - Regular users can only see their own feedback
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        entity_desc = f"deal {deal_id}" if deal_id else f"customer {customer_id}"
        logger.info(f"📝 Getting feedback for {entity_desc} by {user_email}")

        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        all_feedback = await feedback_repo.get_feedback_by_customer(conn, customer_id, category, deal_id)

        # Filter based on role
        user_is_admin = await is_admin(conn, user_email)

        if user_is_admin:
            filtered_feedback = all_feedback
        else:
            filtered_feedback = [f for f in all_feedback if f['employee_id'] == employee_id]

        items = [
            FeedbackResponse(
                feedback_id=f['feedback_id'],
                customer_id=f['customer_id'],
                deal_id=f.get('deal_id'),
                feedback_category=f['feedback_category'],
                employee_id=f['employee_id'],
                rating=f['rating'],
                feedback_history=f.get('feedback_history', []),
                ai_summary=f.get('ai_summary'),
                created_at=f['created_at'].isoformat() if f['created_at'] else None,
                updated_at=f['updated_at'].isoformat() if f['updated_at'] else None,
                employee_name=f.get('employee_name'),
                employee_email=f.get('employee_email')
            )
            for f in filtered_feedback
        ]

        if page is not None and per_page is not None:
            total = len(items)
            start = (page - 1) * per_page
            end = start + per_page
            return paginated_response(items[start:end], total, page, per_page, key="feedback")

        return items

    except HTTPException as he:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback_by_id(
    feedback_id: int,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Get specific feedback by ID.

    - Users can only view their own feedback unless they are admin

    - **feedback_id**: Feedback ID
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting feedback {feedback_id} by {user_email}")

        # Get employee ID
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get feedback
        feedback = await feedback_repo.get_feedback_by_id(conn, feedback_id)

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Check permissions
        if not await is_admin(conn, user_email) and feedback['employee_id'] != employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own feedback")

        return FeedbackResponse(
            feedback_id=feedback['feedback_id'],
            customer_id=feedback['customer_id'],
            deal_id=feedback.get('deal_id'),
            feedback_category=feedback['feedback_category'],
            employee_id=feedback['employee_id'],
            rating=feedback['rating'],
            feedback_history=feedback.get('feedback_history', []),
            ai_summary=feedback.get('ai_summary'),
            created_at=feedback['created_at'].isoformat() if feedback['created_at'] else None,
            updated_at=feedback['updated_at'].isoformat() if feedback['updated_at'] else None,
            employee_name=feedback.get('employee_name'),
            employee_email=feedback.get('employee_email')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback by ID: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: int,
    feedback_data: FeedbackUpdate,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Update existing feedback.

    - Only the owner can update their feedback

    - **feedback_id**: Feedback ID
    - **rating**: New rating (1-5, optional)
    - **feedback_text**: New feedback text (optional)
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Updating feedback {feedback_id} by {user_email}")

        # Validate rating if provided
        if feedback_data.rating is not None and (feedback_data.rating < 1 or feedback_data.rating > 5):
            raise HTTPException(status_code=400, detail="rating must be between 1 and 5")

        # Get employee ID
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check ownership
        if not await check_feedback_ownership(conn, feedback_id, employee_id):
            raise HTTPException(status_code=403, detail="You can only update your own feedback")

        # Update feedback
        result = await feedback_repo.update_feedback(
            conn=conn,
            feedback_id=feedback_id,
            employee_id=employee_id,
            rating=feedback_data.rating,
            feedback_text=feedback_data.feedback_text
        )

        if not result:
            raise HTTPException(status_code=404, detail="Feedback not found or no changes made")

        # Regenerate AI summary after update
        logger.info(f"Regenerating AI summary for updated feedback {result['feedback_id']}")
        ai_summary = feedback_agent.analyze_feedback_history(
            feedback_history=result.get('feedback_history', []),
            current_rating=result['rating'],
            feedback_category=result['feedback_category'],
            customer_id=result['customer_id'],
            deal_id=result.get('deal_id')
        )

        # Update database with new AI summary
        if ai_summary:
            await feedback_repo.update_ai_summary(
                conn=conn,
                feedback_id=result['feedback_id'],
                ai_summary=ai_summary
            )
            result['ai_summary'] = ai_summary
            logger.info(f"✅ AI summary regenerated for feedback {result['feedback_id']}")
        else:
            logger.warning(f"⚠️ No AI summary generated for feedback {result['feedback_id']}")
            result['ai_summary'] = None

        return FeedbackResponse(
            feedback_id=result['feedback_id'],
            customer_id=result['customer_id'],
            deal_id=result.get('deal_id'),
            feedback_category=result['feedback_category'],
            employee_id=result['employee_id'],
            rating=result['rating'],
            feedback_history=result.get('feedback_history', []),
            ai_summary=result.get('ai_summary'),
            created_at=result['created_at'].isoformat() if result['created_at'] else None,
            updated_at=result['updated_at'].isoformat() if result['updated_at'] else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Delete feedback.

    - Only the owner can delete their feedback

    - **feedback_id**: Feedback ID
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Deleting feedback {feedback_id} by {user_email}")

        # Get employee ID
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check ownership
        if not await check_feedback_ownership(conn, feedback_id, employee_id):
            raise HTTPException(status_code=403, detail="You can only delete your own feedback")

        # Delete feedback
        success = await feedback_repo.delete_feedback(conn, feedback_id)

        if not success:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return {"success": True, "message": "Feedback deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
