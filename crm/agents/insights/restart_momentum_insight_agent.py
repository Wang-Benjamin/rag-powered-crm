"""
Restart Momentum Insight Agent - AI-Powered Client Re-engagement Analysis

A specialized AI agent that helps employees restart momentum with inactive clients by analyzing
why clients may have become inactive and generating actionable insights to re-engage them.
This agent focuses on clients with no interactions in the last 30 days who have active deals,
providing strategic recommendations to restart productive relationships.

Business Rule Implementation:
- Automatically selected for customers with NO interactions in the last 30 days AND at least one active deal
- Active deals are those with status NOT IN ('Closed-Lost', 'Closed-Won')
- Prioritized over other agents when these conditions are met

This agent is designed for client re-engagement analysis with strict JSON output format,
providing concise insights that focus on relationship recovery and actionable re-engagement strategies.

Key Features:
1. Inactive client analysis with root cause assessment (30-day window)
2. Historical interaction pattern analysis for context
3. Email and note integration for comprehensive client understanding
4. Strategic re-engagement recommendations with specific talking points
5. OpenAI-powered AI analysis

Core Analysis Capabilities:
- Inactive client profiling based on historical engagement patterns
- Root cause analysis for client inactivity using LLM reasoning
- Email communication pattern analysis for relationship context
- Note analysis for understanding client concerns and interests
- Personalized re-engagement strategies and conversation starters
- Actionable recommendations for relationship recovery

Output Format:
Returns exactly one JSON object with Activities, Insights, Next Move, Last Interaction, and Important Notes sections.

Data Integration Strategy:
- PRIMARY: email_agent and note_agent outputs for recent communication context
- SECONDARY: deals.csv and clients.csv for client background and value assessment
- SUPPORTING: Historical interaction patterns for engagement analysis

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""
import logging

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
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class RestartMomentumInsightAgent:
    """
    AI-powered Restart Momentum Insight Agent

    This agent analyzes inactive clients (>30 days since last interaction with active deals) to understand
    why they became inactive and provides strategic insights and actionable recommendations
    to restart momentum and re-engage the client relationship.

    Business Rule: Automatically selected for customers with no interactions in 30 days AND active deals.
    Returns structured JSON output with Activities, Insights, Next Move, Last Interaction, and Important Notes sections.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None,
                 email: str = None):
        """
        Initialize the Restart Momentum Insight Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            email: User email for database routing (required for production)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Restart Momentum Insight Agent",
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
        self.email_agent = EmailAgent(provider=provider, model_name=model_name,
                                    openai_api_key=openai_api_key)
        self.note_agent = NoteAgent(provider=provider, model_name=model_name,
                                  openai_api_key=openai_api_key)



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
            system_message = "You are a senior client relationship manager and re-engagement specialist. You provide structured JSON responses with specific insights and actionable recommendations for restarting momentum with inactive clients. Each insight must contain 1-2 concise sentences. Focus on inactivity pattern analysis, communication content evaluation for root cause identification, and comprehensive re-engagement strategies with integrated reasoning."

        return self.model_factory.generate_content(prompt, system_message)

    def _determine_activities_status(self, client_history: Dict[str, Any]) -> str:
        """
        Determine Activities status based on interaction history
        For RestartMomentumInsightAgent, this should typically be 'inactive' since we focus on inactive clients
        Updated to use 30-day window per business rule requirements

        Returns:
            "inactive" for clients with interactions >30 days old
            "churned" if no interactions exist
            "active" if somehow recent interactions exist (edge case)
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

        # Check if within 30 days (updated from 7 days per business rule)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        if most_recent >= thirty_days_ago:
            return "active"  # Edge case - shouldn't happen for this agent's intended use
        else:
            return "inactive"

    def format_client_data_for_analysis(self, client_history: Dict[str, Any]) -> str:
        """
        Format client history data focusing on inactivity analysis and re-engagement context

        Args:
            client_history: Complete client history data structure

        Returns:
            Formatted string optimized for restart momentum analysis
        """
        if not client_history:
            return "No client history data available for analysis."

        # Extract key information
        client_info = client_history.get("client_info", {})
        client_details = client_history.get("client_details", {})
        deals = client_history.get("deals", [])
        interactions = client_history.get("interaction_details", [])
        notes = client_history.get("employee_client_notes", [])
        metrics = client_history.get("summary_metrics", {})

        # Calculate inactivity metrics
        total_interactions = len(interactions)
        last_interaction_date = "N/A"
        days_since_last_interaction = 0

        if interactions:
            # Sort interactions by date to find the most recent
            sorted_interactions = sorted(interactions, key=lambda x: x.get('created_at', ''), reverse=True)
            last_interaction = sorted_interactions[0]
            last_interaction_date = last_interaction.get('created_at', 'N/A')

            # Calculate days since last interaction
            if last_interaction_date != 'N/A':
                try:
                    if isinstance(last_interaction_date, str):
                        last_dt = datetime.fromisoformat(last_interaction_date.replace('Z', '+00:00'))
                    else:
                        last_dt = last_interaction_date
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    days_since_last_interaction = (datetime.now(timezone.utc) - last_dt).days
                except:
                    days_since_last_interaction = 0

        # Calculate deal metrics
        total_deals = len(deals)
        won_deals = [d for d in deals if d.get('room_status') == 'closed-won']
        won_value = sum(d.get('value_usd', 0) for d in won_deals)

        # Get client value information from deals
        total_deal_value = sum(d.get('value_usd', 0) for d in deals)

        # Determine activity status
        activities_status = self._determine_activities_status(client_history)

        # Calculate active deals (excluding closed-lost and closed-won)
        active_deals = [d for d in deals if d.get('room_status') not in ['closed-won', 'closed-lost']]
        active_deal_value = sum(d.get('value_usd', 0) for d in active_deals)

        formatted_data = f"""
=== CLIENT RESTART MOMENTUM ANALYSIS (30-DAY BUSINESS RULE) ===
Company: {client_info.get('name', 'N/A')}
Activity Status: {activities_status}
Days Since Last Interaction: {days_since_last_interaction} days
Last Interaction Date: {last_interaction_date}
Total Historical Interactions: {total_interactions}

=== CLIENT VALUE ASSESSMENT ===
Total Deal Value: ${total_deal_value:,.2f}
Historical Won Deals: {len(won_deals)} (${won_value:,.2f} total value)
Active Deals: {len(active_deals)} (${active_deal_value:,.2f} total value)

=== INACTIVITY CONTEXT (30-DAY RULE) ===
Client Status: {client_info.get('status', 'N/A')}
Total Notes: {len(notes)}
Total Deals: {total_deals}
Active Deals (Non-Closed): {len(active_deals)}
Client Type: {client_info.get('client_type', 'N/A')}
Restart Momentum Trigger: No interactions in 30+ days with active deals

=== RECENT INTERACTION HISTORY ===
"""

        # Add recent interaction details (last 3 interactions)
        if interactions:
            recent_interactions = sorted(interactions, key=lambda x: x.get('created_at', ''), reverse=True)[:3]
            for i, interaction in enumerate(recent_interactions, 1):
                days_ago = 0
                try:
                    if isinstance(interaction.get('created_at'), str):
                        int_dt = datetime.fromisoformat(interaction.get('created_at', '').replace('Z', '+00:00'))
                    else:
                        int_dt = interaction.get('created_at')
                    if int_dt.tzinfo is None:
                        int_dt = int_dt.replace(tzinfo=timezone.utc)
                    days_ago = (datetime.now(timezone.utc) - int_dt).days
                except:
                    pass

                formatted_data += f"Interaction {i} ({days_ago} days ago): {interaction.get('type', 'Unknown')} - {interaction.get('content', 'No content')[:100]}{'...' if len(interaction.get('content', '')) > 100 else ''}\n"
        else:
            formatted_data += "No interaction history available.\n"

        return formatted_data

    async def generate_restart_momentum_insights(self,
                                         conn: asyncpg.Connection,
                                         client_history: Dict[str, Any],
                                         employee_id: int = None) -> str:
        """
        Generate restart momentum insights with strict JSON output format

        This method integrates email_agent and note_agent outputs to provide comprehensive
        analysis of why a client became inactive and actionable recommendations to restart momentum.

        Args:
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering communications

        Returns:
            JSON string with Activities, Insights, Next Move, Last Interaction, and Important Notes sections
        """
        # Get formatted data for analysis
        formatted_data = self.format_client_data_for_analysis(client_history)

        # Determine client_id for agent integration
        client_id = client_history.get("client_info", {}).get("client_id")
        if not client_id:
            return json.dumps({
                "error": "Client ID not found in client history data",
                "Activities": "churned",
                "Insights": [
                    "Inactivity Analysis: Unable to analyze client inactivity patterns and engagement indicators without valid client identification data. The system requires proper client ID to access historical communication records and evaluate engagement patterns. Data validation and client record verification are needed before proceeding with inactivity analysis.",
                    "Communication Content Analysis: Cannot examine email content and note content to identify root causes of client inactivity without access to client communication records. The system needs valid client identification to analyze communication gaps, unaddressed concerns, and relationship deterioration patterns. Client data integrity must be established for accurate content analysis.",
                    "Re-engagement Strategy: Unable to develop targeted re-engagement approaches without access to client historical engagement patterns and communication preferences data. The system requires valid client identification to analyze past successful engagement methods and customize reactivation strategies. Proper client data validation is essential for effective re-engagement planning."
                ],
                "Next Move": [
                    "Verify client data integrity and ensure proper client ID is available in the system, as this is essential for accessing historical interaction records and developing accurate re-engagement analysis based on client-specific patterns and preferences",
                    "Contact system administrator to resolve client data validation issues and ensure all required client identification fields are properly populated before attempting restart momentum analysis"
                ],
                "Last Interaction": "N/A - Client data validation required",
                "Important Notes": "Data validation required - cannot proceed without valid client ID"
            })

        # PARALLEL EXECUTION: Run email and note analysis concurrently
        logger.info(f"🚀 RestartMomentumInsightAgent [Customer {client_id}]: Starting PARALLEL sub-agent execution")
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
                logger.info(f"✅ RestartMomentumInsightAgent [Customer {client_id}]: Email analysis completed successfully")
            except Exception as e:
                logger.error(f"❌ RestartMomentumInsightAgent [Customer {client_id}]: Email analysis failed: {str(e)}")
                import traceback
                logger.error(f"🔍 RestartMomentumInsightAgent [Customer {client_id}]: Email analysis traceback: {traceback.format_exc()}")
                email_analysis = {"error": f"Email analysis failed: {str(e)}"}

            try:
                note_analysis = note_future.result()
                logger.info(f"✅ RestartMomentumInsightAgent [Customer {client_id}]: Note analysis completed successfully")
            except Exception as e:
                logger.error(f"❌ RestartMomentumInsightAgent [Customer {client_id}]: Note analysis failed: {str(e)}")
                import traceback
                logger.error(f"🔍 RestartMomentumInsightAgent [Customer {client_id}]: Note analysis traceback: {traceback.format_exc()}")
                note_analysis = {"error": f"Note analysis failed: {str(e)}"}

        parallel_time = (datetime.now(timezone.utc) - parallel_start_time).total_seconds()
        logger.info(f"⚡ RestartMomentumInsightAgent [Customer {client_id}]: PARALLEL execution completed in {parallel_time:.2f}s")
        logger.info(f"📊 RestartMomentumInsightAgent [Customer {client_id}]: Email analysis keys: {list(email_analysis.keys()) if isinstance(email_analysis, dict) else 'Not a dict'}")
        logger.info(f"📊 RestartMomentumInsightAgent [Customer {client_id}]: Note analysis keys: {list(note_analysis.keys()) if isinstance(note_analysis, dict) else 'Not a dict'}")

        # Fetch user preferences and feedback
        user_preferences = await self._get_user_preferences_summary(conn)
        crm_ai_insights_prefs = await self._get_crm_category_preferences(conn, 'ai_insights')
        crm_feedback_summary = await self._get_crm_feedback_summary(conn, client_id)

        # Determine activities status
        activities_status = self._determine_activities_status(client_history)

        system_message = """You are a senior client strategist specializing in re-engagement. Return exactly one valid JSON object — no markdown, no extra text.

CORE RULES:
- Be SPECIFIC: always include names, dollar amounts, dates, and percentages from the data
- Be DIRECT: explain why engagement dropped and what concrete action to take
- NEVER say "the client" when you have their name — use it
- Reference the LAST meaningful interaction by date and content
- churn_risk must be "low", "medium", or "high" based on actual inactivity duration and deal status

USER PREFERENCES INTEGRATION:
If USER COMMUNICATION PREFERENCES are provided, adapt your tone, formality, and focus areas accordingly.
If CRM AI INSIGHTS PREFERENCES are provided, adjust detail_level, actionability, and focus_areas to match.
If HISTORICAL FEEDBACK is provided, learn from past ratings — reinforce approaches with high ratings, adjust for low ratings."""

        prompt = f"""Analyze this inactive client data and return one JSON object.

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
  "churn_risk": "low, medium, or high",
  "Insights": [
    "3 insights, each 2-3 sentences with SPECIFIC details (names, $amounts, dates)",
    "focus on: when and why engagement dropped, what was left unfinished, what hooks exist for re-engagement",
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
5. Reference the last interaction date and content to explain the gap
6. Next steps must name the person, the action, and a concrete re-engagement approach
7. Escape strings properly (use \\n for newlines)"""

        return self._generate_content(prompt, system_message)

    async def generate_quick_insights(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Generate quick restart momentum insights with JSON format

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted restart momentum insights
        """
        return await self.generate_restart_momentum_insights(conn, client_history, employee_id)

    async def analyze_client_inactivity(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Analyze client inactivity patterns with JSON format (same as generate_restart_momentum_insights)

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted inactivity analysis
        """
        return await self.generate_restart_momentum_insights(conn, client_history, employee_id)

    async def generate_reengagement_strategy(self, conn: asyncpg.Connection, client_history: Dict[str, Any], employee_id: int = None) -> str:
        """
        Generate re-engagement strategy with JSON format (same as generate_restart_momentum_insights)

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data
            employee_id: Optional specific employee ID for filtering

        Returns:
            JSON formatted re-engagement strategy
        """
        return await self.generate_restart_momentum_insights(conn, client_history, employee_id)