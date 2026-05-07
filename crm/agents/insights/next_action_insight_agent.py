"""
Next Action Insight Agent - Enhanced AI-Powered Active Client Engagement Analysis

A specialized AI agent that helps employees determine the best next actions for active clients
by analyzing recent interactions and notes from the past week. This agent focuses on clients
with interactions within the last 7 days and provides strategic recommendations with clear
data-driven reasoning to maintain momentum and drive productive engagement forward.

This agent is designed for active client engagement analysis with strict JSON output format,
providing concise insights that focus on maintaining momentum and optimizing next steps with
well-reasoned recommendations.

Enhanced Key Features:
1. Active client analysis with recent interaction focus
2. Recent communication pattern analysis (past 7 days)
3. Email and note integration for comprehensive current context
4. Strategic next action recommendations with clear data-driven reasoning
5. Streamlined output focusing on essential insights and actions
6. OpenAI-powered AI analysis

Core Analysis Capabilities:
- Active client profiling based on recent engagement patterns
- Recent interaction analysis for momentum assessment
- Email communication analysis for current relationship context
- Note analysis for understanding immediate client needs and priorities
- Next action prioritization with reasoning based on data analysis
- Actionable recommendations with clear explanations connecting back to client insights

Enhanced Output Format:
Returns exactly one JSON object with Activities, Insights, and Next Move sections.
Each Next Move recommendation includes clear reasoning that connects back to the data analysis.

Data Integration Strategy:
- PRIMARY: email_agent and note_agent outputs for recent communication context (past 7 days)
- SECONDARY: deals.csv and clients.csv for client background and opportunity assessment
- SUPPORTING: Recent interaction patterns for momentum analysis

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import asyncpg
from agents.communication.email_agent import EmailAgent
from agents.communication.note_agent import NoteAgent
from agents.core.model_factory import ModelFactory

# Load environment variables from .env file
load_dotenv()


class NextActionInsightAgent:
    """
    AI-powered Next Action Insight Agent

    This agent analyzes active clients (interactions within last 7 days) to understand
    current momentum and provides strategic insights and actionable recommendations
    for the next best actions to maintain and accelerate client engagement.
    Returns structured JSON output with Activities, Insights, and Next Move sections.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None,
                 email: str = None):
        """
        Initialize the Next Action Insight Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            email: User email for database routing (required for production)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Next Action Insight Agent",
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key
        )

        # Get model info for backward compatibility
        model_info = self.model_factory.get_model_info()
        self.provider = model_info.provider
        self.model_name = model_info.model_name
        self.client = model_info.client  # For OpenAI

        # Store email for database routing
        self.email = email

        # Initialize email and note agents for integration
        import logging
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"🔧 NextActionInsightAgent: Initializing email and note agents with provider={provider}, model={model_name}")

        try:
            self.email_agent = EmailAgent(provider=provider, model_name=model_name,
                                        openai_api_key=openai_api_key)
            self.logger.info(f"✅ NextActionInsightAgent: EmailAgent initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ NextActionInsightAgent: EmailAgent initialization failed: {e}")
            raise

        try:
            self.note_agent = NoteAgent(provider=provider, model_name=model_name,
                                      openai_api_key=openai_api_key)
            self.logger.info(f"✅ NextActionInsightAgent: NoteAgent initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ NextActionInsightAgent: NoteAgent initialization failed: {e}")
            raise



    async def _get_user_preferences_summary(self, conn: asyncpg.Connection) -> Optional[Dict[str, Any]]:
        """Fetch user AI preferences summary (ai_summary column)."""
        if not self.email:
            return None
        try:
            from data.repositories.user_preferences_repository import UserPreferencesRepository
            return await UserPreferencesRepository().get_ai_preferences_summary(conn, self.email)
        except Exception:
            return None

    async def _get_crm_category_preferences(self, conn: asyncpg.Connection, category: str) -> Optional[Dict[str, Any]]:
        """Fetch CRM category-specific learned preferences."""
        if not self.email:
            return None
        try:
            from data.repositories.user_preferences_repository import UserPreferencesRepository
            return await UserPreferencesRepository().get_category_preferences(conn, self.email, category)
        except Exception:
            return None

    async def _get_crm_feedback_summary(self, conn: asyncpg.Connection, customer_id: int) -> Optional[Dict[str, Any]]:
        """Fetch recent + highly-rated feedback AI summaries for a customer."""
        if not self.email:
            return None
        try:
            from data.repositories.feedback_repository import FeedbackRepository
            feedback_list = await FeedbackRepository().get_feedback_by_customer(conn=conn, customer_id=customer_id)
            if not feedback_list:
                return None
            with_summary = [f for f in feedback_list if f.get('ai_summary') is not None]
            if not with_summary:
                return None
            sorted_fb = sorted(with_summary, key=lambda x: x.get('created_at', ''), reverse=True)
            result = {}
            result['recent'] = [{'category': f.get('feedback_category'), 'rating': f.get('rating'),
                                 'ai_summary': f.get('ai_summary'), 'created_at': str(f.get('created_at', ''))}
                                for f in sorted_fb[:5]]
            highly_rated = [{'category': f.get('feedback_category'), 'rating': f.get('rating'),
                            'ai_summary': f.get('ai_summary'), 'created_at': str(f.get('created_at', ''))}
                           for f in sorted_fb if f.get('rating', 0) >= 4]
            if highly_rated:
                result['highly_rated'] = highly_rated
            return result if result else None
        except Exception:
            return None

    def _generate_content(self, prompt: str, system_message: str = None) -> str:
        """
        Generate content using the selected provider with enhanced error handling

        Args:
            prompt: The user prompt
            system_message: Optional system message for better context
        """
        if system_message is None:
            system_message = "You are a senior client success manager and engagement strategist. You provide structured JSON responses with specific insights and actionable recommendations with clear data-driven reasoning for maintaining momentum with active clients. Each insight must contain 1-2 concise sentences. Focus on next best actions and strategic engagement optimization with reasoning that connects back to client data analysis."

        return self.model_factory.generate_content(prompt, system_message)

    def _determine_activities_status(self, client_history: Dict[str, Any]) -> str:
        """
        Determine Activities status based on interaction history
        For NextActionInsightAgent, this should typically be 'active' since we focus on active clients

        Updated to use 14-day window to match the agent selection criteria.

        Returns:
            "active" for clients with interactions within last 14 days
            "inactive" for clients with interactions >14 days old
            "churned" if no interactions exist
        """
        from datetime import datetime, timedelta

        interactions = client_history.get("interaction_details", [])

        if not interactions:
            return "churned"

        # Find most recent interaction
        most_recent = None
        for interaction in interactions:
            created_at = interaction.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        continue
                elif hasattr(created_at, 'date'):
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                else:
                    continue

                if most_recent is None or created_at > most_recent:
                    most_recent = created_at

        if most_recent is None:
            return "decline"

        # Check if within 14 days (matching agent selection criteria)
        fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
        if most_recent >= fourteen_days_ago:
            return "active"
        else:
            return "inactive"  # Edge case - shouldn't happen for this agent's intended use

    def format_client_data_for_analysis(self, client_history: Dict[str, Any]) -> str:
        """
        Format client history data for next action analysis.

        When RAG is enabled, the data is already relevance-ranked, so we show
        all provided items rather than filtering to a narrow time window.

        Args:
            client_history: Complete client history data structure

        Returns:
            Formatted string optimized for next action analysis
        """
        if not client_history:
            return "No client history data available for analysis."

        # Extract key information
        client_info = client_history.get("client_info", {})
        client_details = client_history.get("client_details", {})
        deals = client_history.get("deals", [])
        interactions = client_history.get("interaction_details", [])
        emails = client_history.get("crm_emails", [])
        notes = client_history.get("employee_client_notes", [])
        metrics = client_history.get("summary_metrics", {})

        # Calculate deal metrics
        active_deals = [d for d in deals if d.get('room_status') not in ['closed-won', 'closed-lost']]
        won_deals = [d for d in deals if d.get('room_status') == 'closed-won']
        active_deal_value = sum(d.get('value_usd', 0) for d in active_deals)

        activities_status = self._determine_activities_status(client_history)

        formatted_data = f"""
=== CLIENT NEXT ACTION ANALYSIS ===
Company: {client_info.get('name', 'N/A')}
Activity Status: {activities_status}
Client Status: {client_info.get('status', 'N/A')}

=== DEAL PIPELINE ===
Active Deals: {len(active_deals)} (${active_deal_value:,.2f} total value)
Historical Won Deals: {len(won_deals)}
Total Deals: {len(deals)}

=== COMMUNICATION SUMMARY ===
Emails: {len(emails)} | Interactions (calls/meetings): {len(interactions)} | Notes: {len(notes)}
"""

        # Show top emails (already relevance-ranked by RAG)
        if emails:
            formatted_data += "\n=== KEY EMAILS (relevance-ranked) ===\n"
            for i, email in enumerate(emails[:8], 1):
                body = email.get('body') or email.get('content') or ''
                formatted_data += (
                    f"\nEmail {i}: {email.get('subject', '(no subject)')}\n"
                    f"  Direction: {email.get('direction', '?')} | Date: {email.get('created_at', 'N/A')}\n"
                    f"  From: {email.get('from_email', '')} → To: {email.get('to_email', '')}\n"
                    f"  Content: {body[:300]}{'...' if len(body) > 300 else ''}\n"
                )

        # Show top interactions (calls/meetings)
        if interactions:
            formatted_data += "\n=== KEY INTERACTIONS (calls/meetings, relevance-ranked) ===\n"
            for i, interaction in enumerate(interactions[:5], 1):
                content = interaction.get('content') or ''
                formatted_data += (
                    f"\nInteraction {i}: {interaction.get('type', 'Unknown')} | Date: {interaction.get('created_at', 'N/A')}\n"
                    f"  Content: {content[:300]}{'...' if len(content) > 300 else ''}\n"
                )

        # Show top notes
        if notes:
            formatted_data += "\n=== KEY NOTES (relevance-ranked) ===\n"
            for i, note in enumerate(notes[:8], 1):
                body = note.get('body') or ''
                formatted_data += (
                    f"\nNote {i}: {note.get('title', 'Untitled')} | Date: {note.get('created_at', 'N/A')}\n"
                    f"  Content: {body[:300]}{'...' if len(body) > 300 else ''}\n"
                )

        return formatted_data

    async def generate_next_action_insights(self,
                                    conn: asyncpg.Connection,
                                    client_history: Dict[str, Any],
                                    employee_id: int = None) -> str:
        """
        Generate next action insights with strict JSON output format

        This method integrates email_agent and note_agent outputs to provide comprehensive
        analysis of current client momentum and actionable recommendations for next best actions.

        Args:
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering communications

        Returns:
            JSON string with Activities, Insights, and Next Move sections
        """
        # Get formatted data for analysis
        formatted_data = self.format_client_data_for_analysis(client_history)

        # Determine client_id for agent integration
        client_id = client_history.get("client_info", {}).get("client_id")
        if not client_id:
            return json.dumps({
                "error": "Client ID not found in client history data",
                "Activities": "decline",
                "Insights": ["Unable to analyze client without valid client ID"],
                "Next Move": ["Verify client data and try again"]
            })

        # PARALLEL EXECUTION: Run email and note analysis concurrently
        self.logger.info(f"🚀 NextActionInsightAgent [Customer {client_id}]: Starting PARALLEL sub-agent execution")
        parallel_start_time = datetime.now(timezone.utc)

        # Execute all analyses in parallel using concurrent.futures
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all tasks
            email_future = executor.submit(
                lambda: self.email_agent.analyze_email_communications(
                    client_history.get("crm_emails", []),
                    client_id,
                    analysis_focus="comprehensive",
                    employee_id=employee_id
                ) if client_history.get("crm_emails", []) else {}
            )

            note_future = executor.submit(
                lambda: self.note_agent.analyze_client_notes(
                    client_history.get("employee_client_notes", []),
                    client_id,
                    analysis_focus="comprehensive",
                    employee_id=employee_id
                ) if client_history.get("employee_client_notes", []) else {}
            )

            # Get results with INDEPENDENT error handling for each future
            try:
                email_analysis = email_future.result()
                self.logger.info(f"✅ NextActionInsightAgent [Customer {client_id}]: Email analysis completed successfully")
            except Exception as e:
                self.logger.error(f"❌ NextActionInsightAgent [Customer {client_id}]: Email analysis failed: {str(e)}")
                import traceback
                self.logger.error(f"🔍 NextActionInsightAgent [Customer {client_id}]: Email analysis traceback: {traceback.format_exc()}")
                email_analysis = {"error": f"Email analysis failed: {str(e)}"}

            try:
                note_analysis = note_future.result()
                self.logger.info(f"✅ NextActionInsightAgent [Customer {client_id}]: Note analysis completed successfully")
            except Exception as e:
                self.logger.error(f"❌ NextActionInsightAgent [Customer {client_id}]: Note analysis failed: {str(e)}")
                import traceback
                self.logger.error(f"🔍 NextActionInsightAgent [Customer {client_id}]: Note analysis traceback: {traceback.format_exc()}")
                note_analysis = {"error": f"Note analysis failed: {str(e)}"}

        parallel_time = (datetime.now(timezone.utc) - parallel_start_time).total_seconds()
        self.logger.info(f"⚡ NextActionInsightAgent [Customer {client_id}]: PARALLEL execution completed in {parallel_time:.2f}s")
        self.logger.info(f"📊 NextActionInsightAgent [Customer {client_id}]: Email analysis keys: {list(email_analysis.keys()) if isinstance(email_analysis, dict) else 'Not a dict'}")
        self.logger.info(f"📊 NextActionInsightAgent [Customer {client_id}]: Note analysis keys: {list(note_analysis.keys()) if isinstance(note_analysis, dict) else 'Not a dict'}")

        # Fetch user preferences and feedback
        user_preferences = await self._get_user_preferences_summary(conn)
        crm_ai_insights_prefs = await self._get_crm_category_preferences(conn, 'ai_insights')
        crm_feedback_summary = await self._get_crm_feedback_summary(conn, client_id)

        # Determine activities status
        activities_status = self._determine_activities_status(client_history)

        system_message = """You are a senior client strategist. Return exactly one valid JSON object — no markdown, no extra text.

CORE RULES:
- Be SPECIFIC: always include names, dollar amounts, dates, and percentages from the data
- Be DIRECT: state what happened and what to do, not vague observations
- NEVER say "the client" when you have their name — use it
- NEVER say "revised terms" when you have the numbers — cite them
- churn_risk must be "low" or "medium" only (never "high" for active customers)

USER PREFERENCES INTEGRATION:
If USER COMMUNICATION PREFERENCES are provided, adapt your tone, formality, and focus areas accordingly.
If CRM AI INSIGHTS PREFERENCES are provided, adjust detail_level, actionability, and focus_areas to match.
If HISTORICAL FEEDBACK is provided, learn from past ratings — reinforce approaches with high ratings, adjust for low ratings."""

        prompt = f"""Analyze this client data and return one JSON object.

{formatted_data}

EMAIL ANALYSIS:
{json.dumps(email_analysis, indent=2) if email_analysis else "No email analysis available"}

NOTE ANALYSIS:
{json.dumps(note_analysis, indent=2) if note_analysis else "No note analysis available"}

=== USER COMMUNICATION PREFERENCES ===
{json.dumps(user_preferences, indent=2) if user_preferences else "No user preferences configured"}

=== CRM AI INSIGHTS PREFERENCES ===
{json.dumps(crm_ai_insights_prefs, indent=2) if crm_ai_insights_prefs else "No CRM AI insights preferences configured"}

=== HISTORICAL CRM FEEDBACK ===
{json.dumps(crm_feedback_summary, indent=2) if crm_feedback_summary else "No historical feedback available"}

Return this JSON structure:
{{{{
  "Activities": "{activities_status}",
  "churn_risk": "low or medium",
  "Insights": [
    "3 insights, each 2-3 sentences with SPECIFIC details (names, $amounts, dates, percentages)",
    "cover whatever matters most: deal status, risks, stakeholders, wins, blockers, opportunities",
    "do NOT use fixed category labels — just state each insight directly"
  ],
  "Next Move": [
    "2-3 actions, each naming WHO to contact, WHAT to do, and BY WHEN"
  ]
}}}}

REQUIREMENTS:
1. Return ONLY valid JSON — no markdown, no extra text
2. Activities is pre-set as "{activities_status}"
3. Each insight: 2-3 sentences with specific names, dollar amounts, dates from the data
4. Write exactly 3 insights covering the most important findings — no fixed categories
5. Next steps must name the person, the action, and the deadline
6. Escape strings properly (use \\n for newlines)"""

        response = self._generate_content(prompt, system_message)

        # Clean and validate JSON response
        try:
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            # Fix common JSON issues - just handle the most common case
            # Replace literal newline characters within JSON strings
            lines = response_clean.split('\n')
            if len(lines) > 1:
                # If there are actual newlines, this might be multiline JSON - join and clean
                response_clean = ' '.join(line.strip() for line in lines)

            # Validate JSON
            parsed_json = json.loads(response_clean)
            return json.dumps(parsed_json, indent=2)

        except json.JSONDecodeError:
            # Return fallback JSON if parsing fails
            fallback_response = {
                "Activities": activities_status,
                "churn_risk": "medium",  # Default to medium when analysis fails
                "Insights": [
                    "Momentum Assessment: Client interaction quality analysis encountered processing challenges but attempted to evaluate response patterns and engagement indicators. Manual review of client communication sentiment and response timing may be needed.",
                    "Recent Communication Analysis: Communication content analysis was requested but encountered processing difficulties while attempting to evaluate conversation tone and effectiveness. Review of actual conversation content may provide insights.",
                    "Opportunity Identification: Opportunity analysis was initiated but faced processing constraints while attempting to identify immediate relationship advancement possibilities. Direct client consultation may reveal specific opportunities."
                ],
                "Next Move": [
                    "Review client communication history manually to understand interaction quality patterns and identify areas where our responses could be more effective, as automated analysis encountered processing issues that require human assessment of conversation content",
                    "Schedule direct client check-in call to clarify current needs and assess communication effectiveness, as this will provide immediate feedback on relationship quality and help re-establish engagement momentum based on actual client requirements"
                ]
            }
            return json.dumps(fallback_response, indent=2)

    async def generate_quick_insights(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Generate quick next action insights with JSON format

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted next action insights
        """
        return await self.generate_next_action_insights(conn, client_history, employee_id)

    async def analyze_client_momentum(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Analyze client momentum patterns with JSON format (same as generate_next_action_insights)

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted momentum analysis
        """
        return await self.generate_next_action_insights(conn, client_history, employee_id)

    async def generate_engagement_strategy(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Generate engagement strategy with JSON format (same as generate_next_action_insights)

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted engagement strategy
        """
        return await self.generate_next_action_insights(conn, client_history, employee_id)