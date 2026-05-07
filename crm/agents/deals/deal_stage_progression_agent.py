# DEPRECATED: Stage progression replaced by event-driven room_status updates. See docs/pivot/13_DEAL_ROOM_IMPLEMENTATION_PLAN.md
"""
Deal Stage Progression Agent - AI-powered Deal Stage Analysis Engine

A specialized AI agent that analyzes customer communications (emails and notes) to determine
if a deal should progress to a different stage based on concrete evidence from interactions.

Key Features:
1. Analyzes emails and notes for stage progression signals
2. Structured JSON output with stage recommendations
3. OpenAI-powered AI analysis
4. Evidence-based reasoning with confidence levels
5. Respects stage progression flow (Opportunity → Discovery → Negotiation → Closed)

Stage Definitions:
- Opportunity: Initial contact, exploring potential fit
- Discovery: Active needs assessment, product demonstrations, requirements gathering
- Negotiation: Proposal sent, pricing discussions, contract terms being discussed
- Closed-Won: Contract signed, deal successfully closed
- Closed-Lost: Deal lost to competitor, customer declined, or no longer pursuing

Required Output Format:
{
  "deal_id": int,
  "current_stage": str,
  "recommended_stage": str,
  "should_update": bool,
  "confidence": str,  # "high", "medium", "low"
  "reasoning": str,
  "evidence": [{"source": str, "source_id": int, "excerpt": str, "signal": str}],
  "timestamp": datetime
}

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""

import os
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from datetime import datetime, timezone
import asyncpg
from agents.core.model_factory import ModelFactory

# Load environment variables
load_dotenv()


class DealStageProgressionAgent:
    """
    AI-powered Deal Stage Progression Agent
    
    Analyzes customer communications to recommend deal stage updates based on
    concrete evidence from emails and notes.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None,
                 email: str = None):
        """
        Initialize the Deal Stage Progression Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            email: User email for database routing and preferences lookup
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Deal Stage Progression Agent",
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key
        )

        # Get model info for backward compatibility
        model_info = self.model_factory.get_model_info()
        self.provider = model_info.provider
        self.model_name = model_info.model_name
        self.client = model_info.client  # For OpenAI

        # Store email for preferences lookup
        self.email = email

    async def _get_crm_category_preferences(self, conn: asyncpg.Connection, category: str):
        """
        Fetch CRM category-specific preferences from user_preferences table.

        Args:
            conn: asyncpg database connection
            category: Category name ('churn_risk', 'ai_insights', 'stage_progression', 'deal_insights')

        Returns:
            Dictionary with category preference data or None
        """
        import logging
        agent_logger = logging.getLogger(__name__)

        if not self.email:
            agent_logger.warning("No user email available for CRM preferences lookup")
            return None

        try:
            from data.repositories.user_preferences_repository import UserPreferencesRepository
            prefs_repo = UserPreferencesRepository()
            result = await prefs_repo.get_category_preferences(conn, self.email, category)
            if result:
                agent_logger.info(f"Loaded CRM {category} preferences for user {self.email}")
            else:
                agent_logger.info(f"No CRM {category} preferences found for user {self.email}")
            return result
        except Exception as e:
            agent_logger.warning(f"Failed to fetch CRM {category} preferences: {e}")
            return None

    def _generate_content(self, prompt: str, system_message: str = None) -> str:
        """
        Generate content using the selected provider with enhanced error handling

        Args:
            prompt: The user prompt
            system_message: Optional system message for better context
        """
        if system_message is None:
            system_message = """You are an expert sales process analyst specializing in deal stage progression. 
Your task is to analyze customer communications (emails and notes) and determine if a deal should progress 
to a different stage based on concrete evidence. You must follow the specified JSON output format exactly."""

        return self.model_factory.generate_content(prompt, system_message)

    def _format_emails_for_analysis(self, emails: List[Dict[str, Any]]) -> str:
        """
        Format email data for LLM analysis
        
        Args:
            emails: List of email interaction records
            
        Returns:
            Formatted string ready for LLM processing
        """
        if not emails:
            return "No email interactions available."

        formatted = ""
        for i, email in enumerate(emails[:10], 1):  # Limit to 10 most recent
            created_at = email.get('created_at', 'N/A')
            if isinstance(created_at, datetime):
                created_at = created_at.strftime('%Y-%m-%d')
            elif isinstance(created_at, str):
                created_at = created_at[:10]
            
            content = email.get('content', '')[:500]  # Limit content length
            
            formatted += f"""
Email #{i}:
  Date: {created_at}
  Type: {email.get('type', 'communication')}
  Content: {content}{'...' if len(email.get('content', '')) > 500 else ''}
"""
        
        return formatted

    def _format_notes_for_analysis(self, notes: List[Dict[str, Any]]) -> str:
        """
        Format note data for LLM analysis
        
        Args:
            notes: List of note records
            
        Returns:
            Formatted string ready for LLM processing
        """
        if not notes:
            return "No notes available."

        formatted = ""
        for i, note in enumerate(notes[:10], 1):  # Limit to 10 most recent
            created_at = note.get('created_at', 'N/A')
            if isinstance(created_at, datetime):
                created_at = created_at.strftime('%Y-%m-%d')
            elif isinstance(created_at, str):
                created_at = created_at[:10]
            
            title = note.get('title', 'Untitled')
            body = note.get('body', '')[:500]  # Limit content length
            
            formatted += f"""
Note #{i}:
  Date: {created_at}
  Title: {title}
  Content: {body}{'...' if len(note.get('body', '')) > 500 else ''}
"""
        
        return formatted

    async def analyze_deal_stage_progression(self, deal_data: Dict[str, Any], conn: asyncpg.Connection = None) -> Dict[str, Any]:
        """
        Analyze deal communications and recommend stage progression
        
        Args:
            deal_data: Dictionary containing:
                - deal_id: int
                - deal_name: str
                - current_stage: str
                - client_id: int
                - employee_id: int
                - emails: List[Dict]
                - notes: List[Dict]
                - deal_metadata: Dict (value_usd, expected_close_date, etc.)
                
        Returns:
            Dictionary with stage recommendation and reasoning
        """
        import logging
        logger = logging.getLogger(__name__)

        deal_id = deal_data.get('deal_id')
        current_stage = deal_data.get('current_stage')
        
        logger.info(f"🔍 DealStageAgent [Deal {deal_id}]: Starting analysis for stage '{current_stage}'")

        # Extract data
        emails = deal_data.get('emails', [])
        notes = deal_data.get('notes', [])
        deal_metadata = deal_data.get('deal_metadata', {})
        
        logger.info(f"📊 DealStageAgent [Deal {deal_id}]: {len(emails)} emails, {len(notes)} notes")

        # Format communications
        formatted_emails = self._format_emails_for_analysis(emails)
        formatted_notes = self._format_notes_for_analysis(notes)

        # Get CRM category preferences for stage progression
        crm_stage_prefs = await self._get_crm_category_preferences(conn, 'stage_progression') if conn else None

        # Build system message
        system_message = """You are an expert sales process analyst specializing in deal stage progression.
Your task is to analyze customer communications (emails and notes) and determine if a deal should progress
to a different stage based on concrete evidence.

STAGE DEFINITIONS:
- Opportunity: Initial contact, exploring potential fit
- Discovery: Active needs assessment, product demonstrations, requirements gathering
- Negotiation: Proposal sent, pricing discussions, contract terms being discussed
- Closed-Won: Contract signed, deal successfully closed
- Closed-Lost: Deal lost to competitor, customer declined, or no longer pursuing

CRITICAL RULES:
1. Only recommend stage changes when there is CLEAR evidence in the communications
2. Stages should generally progress forward (Opportunity → Discovery → Negotiation → Closed-Won/Lost)
3. Provide specific excerpts from emails/notes as evidence
4. Assign confidence levels: "high" (explicit signals), "medium" (implicit signals), "low" (weak signals)
5. Return valid JSON only
6. Closed-Won and Closed-Lost are terminal stages - never recommend changes FROM these stages

CRITICAL REQUIREMENT - CRM STAGE PROGRESSION PREFERENCES:
If CRM STAGE PROGRESSION PREFERENCES are provided, you MUST adapt your analysis based on learned user preferences:
- detail_level: Adjust reasoning depth (brief/moderate/detailed) to match user preference
- tone: Match the preferred communication tone (formal/casual/professional)
- actionability: Emphasize actionable evidence if user prefers high actionability
- focus_areas: Prioritize specific stage signals the user cares about
- confidence_threshold: Adjust confidence assessment based on user preference
- preference_summary: Use this as a guide for overall output style
These preferences are learned from user feedback and should significantly influence your response."""

        # Build user prompt
        user_prompt = f"""Analyze the following deal communications and determine if the deal stage should be updated:

CURRENT DEAL INFORMATION:
- Deal ID: {deal_id}
- Deal Name: {deal_data.get('deal_name', 'Unknown')}
- Current Stage: {current_stage}
- Deal Value: ${deal_metadata.get('value_usd', 0):,.2f}
- Expected Close Date: {deal_metadata.get('expected_close_date', 'Not set')}

RECENT EMAILS ({len(emails)} total):
{formatted_emails}

RECENT NOTES ({len(notes)} total):
{formatted_notes}

=== CRM STAGE PROGRESSION PREFERENCES ===
{json.dumps(crm_stage_prefs, indent=2) if crm_stage_prefs else "No CRM stage progression preferences configured"}

REQUIRED JSON OUTPUT FORMAT:
{{
  "deal_id": {deal_id},
  "current_stage": "{current_stage}",
  "recommended_stage": "Opportunity|Discovery|Negotiation|Closed-Won|Closed-Lost",
  "should_update": true|false,
  "confidence": "high|medium|low",
  "reasoning": "Detailed explanation with specific evidence from communications",
  "evidence": [
    {{
      "source": "email|note",
      "source_id": 123,
      "excerpt": "Relevant quote from communication",
      "signal": "proposal_sent|contract_signed|pricing_discussed|demo_scheduled|etc"
    }}
  ]
}}

IMPORTANT:
- Only set should_update=true if there is clear evidence for stage change
- If current_stage is already appropriate, set should_update=false
- Closed-Won and Closed-Lost are terminal - do not recommend changes from these
- Return ONLY valid JSON, no additional text"""

        try:
            response = self._generate_content(user_prompt, system_message)
            
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            result = json.loads(response_clean)
            
            # Add timestamp
            result['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"✅ DealStageAgent [Deal {deal_id}]: Analysis complete - {result.get('recommended_stage')}")
            
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ DealStageAgent [Deal {deal_id}]: JSON parsing failed: {e}")
            # Fallback response
            return {
                "deal_id": deal_id,
                "current_stage": current_stage,
                "recommended_stage": current_stage,
                "should_update": False,
                "confidence": "low",
                "reasoning": "Analysis encountered processing issues. Manual review recommended.",
                "evidence": [],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"❌ DealStageAgent [Deal {deal_id}]: Analysis failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback response
            return {
                "deal_id": deal_id,
                "current_stage": current_stage,
                "recommended_stage": current_stage,
                "should_update": False,
                "confidence": "low",
                "reasoning": f"Analysis error: {str(e)}",
                "evidence": [],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

