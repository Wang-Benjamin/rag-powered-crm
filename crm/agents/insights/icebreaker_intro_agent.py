"""
Icebreaker Intro Agent - Enhanced AI-Powered Customer Engagement Insights

A specialized AI agent that helps employees initiate contact with new customers by generating
personalized insights, conversation starters, news-based icebreakers, and well-reasoned
relationship-building recommendations. This agent analyzes customer background, value potential,
interaction history, and current industry developments to provide actionable icebreaker talking
points with clear reasoning.

This agent is designed for customer engagement analysis with strict JSON output format,
providing comprehensive insights that focus on relationship building, current events as
conversation starters, and actionable engagement strategies with data-driven reasoning.

Enhanced Key Features:
1. Customer background analysis with personalized insights
2. Value potential assessment and opportunity identification
3. Interaction history analysis for relationship context
4. Email analysis integration via EmailAgent sub-agent
5. Note analysis integration via NoteAgent sub-agent
6. Call summary extraction and analysis
7. News-based icebreaker suggestions using recent industry developments
8. Reasoned recommendations with clear data-driven explanations
9. OpenAI-powered AI analysis

Core Analysis Capabilities:
- Customer profiling based on available data only
- Value opportunity identification from actual metrics
- Relationship context analysis from interaction history
- Email communication analysis for customer engagement context
- Note analysis for understanding customer needs and priorities
- Call summary analysis for conversation insights
- Current events and industry news as natural conversation starters
- Personalized icebreaker suggestions with business-appropriate topics
- Actionable recommendations with clear reasoning based on comprehensive data analysis

Enhanced Output Format:
Returns exactly one JSON object with Activities, churn_risk, enhanced Insights, and reasoned Next Move sections.
Each recommendation includes clear reasoning that connects back to the client data analysis.

Insight Categories:
- Historical Success: Past wins with similar industry clients to build confidence
- Prospect Context: Industry trends, market conditions, and prospect-specific observations
- Engagement Opportunity: Recent developments and specific conversation starters

Data Integration Strategy:
- PRIMARY: email_agent and note_agent outputs for communication context
- SECONDARY: call summaries and interaction details for relationship insights
- SUPPORTING: client_info and historical data for background context
- Note: Does NOT analyze deals data (customers have no deal history by design)

Data Priority Strategy:
- Use only available database fields for client-specific insights
- Leverage general industry knowledge for context and engagement suggestions
- Never fabricate specific client relationships or data
- Maintain data privacy and compliance standards
- Provide business-appropriate conversation starters

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import asyncpg
from agents.core.model_factory import ModelFactory
from agents.communication.email_agent import EmailAgent
from agents.communication.note_agent import NoteAgent

# Load environment variables from .env file
load_dotenv()


class IcebreakerIntroAgent:
    """
    Enhanced AI-powered Icebreaker Introduction Agent

    This agent analyzes customer data to generate personalized insights, news-based conversation
    starters, and well-reasoned recommendations that help employees initiate meaningful contact
    with new customers. Returns structured JSON output with Activities, churn_risk, enhanced Insights,
    and reasoned Next Move sections.

    Enhanced Features:
    - Three insight categories: Historical Success, Prospect Context, and Engagement Opportunity
    - News-based conversation starters using recent industry developments
    - Reasoned recommendations with clear data-driven explanations
    - Business-appropriate engagement suggestions for professional conversations
    - Enhanced guidance on how to naturally use current events in client interactions
    - Always sets churn_risk to "low" for new prospects (no deal history = cannot churn)
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None,
                 email: str = None):
        """
        Initialize the Icebreaker Intro Agent with OpenAI support and sub-agents

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            email: User email for database routing (optional, for consistency)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Icebreaker Intro Agent",
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

        # Initialize logger
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"🔧 IcebreakerIntroAgent: Initializing email and note agents with provider={provider}, model={model_name}")

        # Initialize email agent for email analysis
        try:
            self.email_agent = EmailAgent(provider=provider, model_name=model_name, openai_api_key=openai_api_key)
            self.logger.info(f"✅ IcebreakerIntroAgent: EmailAgent initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ IcebreakerIntroAgent: EmailAgent initialization failed: {e}")
            raise

        # Initialize note agent for note analysis
        try:
            self.note_agent = NoteAgent(provider=provider, model_name=model_name, openai_api_key=openai_api_key)
            self.logger.info(f"✅ IcebreakerIntroAgent: NoteAgent initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ IcebreakerIntroAgent: NoteAgent initialization failed: {e}")
            raise

        # Note: No ChurnOrchestrator initialization - IcebreakerIntroAgent handles customers with no deal history

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
            system_message = "You are a senior relationship manager and customer engagement specialist. You provide structured JSON responses with specific insights and actionable recommendations. Never fabricate data not present in the input. Maintain data privacy and avoid sensitive inferences."

        return self.model_factory.generate_content(prompt, system_message)

    def format_customer_data_for_analysis(self, 
                                         customer_data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                                         context: str = "icebreaker_analysis") -> str:
        """
        Format customer data for LLM analysis with comprehensive context
        
        Args:
            customer_data: Customer data (client history dict or list of customers)
            context: Analysis context for the formatting
            
        Returns:
            Formatted string ready for LLM processing
        """
        if not customer_data:
            return "No customer data available for analysis."

        # Handle different input formats
        if isinstance(customer_data, dict):
            # Complete client history format
            client_info = customer_data.get("client_info", {})
            client_details = customer_data.get("client_details", {})
            deals = customer_data.get("deals", [])
            interactions = customer_data.get("interaction_details", [])
            notes = customer_data.get("employee_client_notes", [])
            metrics = customer_data.get("summary_metrics", {})
            is_single_customer = True
        else:
            # List format - for now, take first customer
            customer_data = customer_data[0] if isinstance(customer_data, list) else customer_data
            client_info = customer_data
            client_details = {}
            deals = []
            interactions = []
            notes = []
            metrics = {}
            is_single_customer = True

        formatted_data = f"=== CUSTOMER ICEBREAKER ANALYSIS CONTEXT: {context.upper()} ===\n"
        
        # Customer Profile Section
        formatted_data += f"""
=== CUSTOMER PROFILE ===
Company: {client_info.get('name', 'N/A')}
Primary Contact: {client_info.get('primary_contact', 'N/A')}
Location: {client_info.get('location', 'N/A')}
Status: {client_info.get('status', 'N/A')}
Source: {client_info.get('source', 'N/A')}
Client Type: {client_info.get('client_type', 'N/A')}
Notes: {client_info.get('notes', 'N/A')}
"""

        # Value & Opportunity Assessment with proper None handling
        if client_details or deals:
            # Calculate total deal value from deals list
            total_deal_value = sum(d.get('value_usd', 0) for d in deals)
            health_score = client_details.get('health_score') if client_details else None
            health_score = health_score if health_score is not None else 0

            formatted_data += f"""
=== VALUE & OPPORTUNITY ASSESSMENT ===
Total Deal Value: ${total_deal_value:,.2f}
Health Score: {health_score:.2f}/1.0
"""

        # Deal History and Related Clients Context
        if deals:
            total_deal_value = sum(d.get('value_usd', 0) for d in deals)
            won_deals = [d for d in deals if d.get('room_status') == 'closed-won']
            won_value = sum(d.get('value_usd', 0) for d in won_deals)

            formatted_data += f"""
=== DEAL HISTORY AND RELATED CLIENTS CONTEXT ===
Total Deal Portfolio: ${total_deal_value:,.2f}
Won Deal Value: ${won_value:,.2f}
Number of Deals: {len(deals)}
Won Deals: {len(won_deals)}
Recent Deals:"""

            # Show recent deals (up to 3)
            recent_deals = sorted(deals, key=lambda x: x.get('created_at', ''), reverse=True)[:3]
            for deal in recent_deals:
                status_emoji = "✅" if deal.get('room_status') == 'closed-won' else "❌" if deal.get('room_status') == 'closed-lost' else "🔄"
                formatted_data += f"""
  • {deal.get('deal_name', 'Unnamed Deal')} {status_emoji} - ${deal.get('value_usd', 0):,.2f}
    Room Status: {deal.get('room_status', 'Unknown')} | Created: {deal.get('created_at', 'N/A')}"""

        # Interaction History & Relationship Context
        if interactions:
            total_interaction_time = sum(i.get('duration_minutes', 0) for i in interactions)
            recent_interactions = sorted(interactions, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
            
            formatted_data += f"""
=== INTERACTION HISTORY & RELATIONSHIP CONTEXT ===
Total Interactions: {len(interactions)}
Total Interaction Time: {total_interaction_time} minutes
Recent Interactions:"""
            
            for interaction in recent_interactions:
                formatted_data += f"""
  • {interaction.get('type', 'Unknown')} ({interaction.get('duration_minutes', 0)} min) - {interaction.get('created_at', 'N/A')}
    Content: {interaction.get('content', 'No content')[:80]}{'...' if len(interaction.get('content', '')) > 80 else ''}"""

        # Employee Notes & Research
        if notes:
            recent_notes = sorted(notes, key=lambda x: x.get('created_at', ''), reverse=True)[:5]

            formatted_data += f"""
=== EMPLOYEE NOTES & RESEARCH ===
Total Notes: {len(notes)}
Recent Notes:"""

            for note in recent_notes:
                formatted_data += f"""
  • {note.get('title', 'Untitled')} - {note.get('created_at', 'N/A')}
    Content: {note.get('body', 'No content')[:120]}{'...' if len(note.get('body', '')) > 120 else ''}"""

        return formatted_data

    async def generate_icebreaker_insights(self,
                                   conn: asyncpg.Connection,
                                   customer_data: Union[Dict[str, Any], List[Dict[str, Any]]],
                                   insight_type: str = "comprehensive") -> str:
        """
        Generate personalized icebreaker insights with strict JSON output format

        This method integrates email_agent and note_agent outputs to provide comprehensive
        analysis of new customer context and actionable icebreaker recommendations.

        Args:
            customer_data: Customer data to analyze
            insight_type: Type of insights (currently all return same comprehensive format)

        Returns:
            JSON string with Activities, Insights, and Next Move sections
        """
        # Get formatted data for analysis
        formatted_data = self.format_customer_data_for_analysis(customer_data, context="icebreaker_insights")

        # Determine client_id for agent integration
        client_id = customer_data.get("client_info", {}).get("client_id")
        if not client_id:
            return json.dumps({
                "error": "Client ID not found in customer data",
                "Activities": "decline",
                "churn_risk": "low",
                "Insights": [
                    "Momentum Assessment: Unable to assess engagement without valid client identification.",
                    "Recent Communication Analysis: Customer data validation required before communication analysis can proceed.",
                    "Opportunity Identification: Valid client identification needed to access historical success patterns and opportunity analysis."
                ],
                "Next Move": [
                    "Verify customer data and ensure valid client ID is present in the system. Without proper identification, personalized analysis and opportunity matching cannot be performed effectively.",
                    "Once client ID is verified, re-run analysis to generate momentum assessment, communication insights, and opportunity identification based on available prospect data."
                ]
            })

        # PARALLEL EXECUTION: Run email and note analysis concurrently
        self.logger.info(f"🚀 IcebreakerIntroAgent [Customer {client_id}]: Starting PARALLEL sub-agent execution")
        parallel_start_time = datetime.now(timezone.utc)

        # Execute both analyses in parallel using concurrent.futures
        try:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks
                email_future = executor.submit(
                    lambda: self.email_agent.analyze_email_communications(
                        customer_data.get("crm_emails", []),
                        client_id,
                        analysis_focus="comprehensive",
                        employee_id=None
                    ) if customer_data.get("crm_emails", []) else {}
                )

                note_future = executor.submit(
                    lambda: self.note_agent.analyze_client_notes(
                        customer_data.get("employee_client_notes", []),
                        client_id,
                        analysis_focus="comprehensive",
                        employee_id=None
                    ) if customer_data.get("employee_client_notes", []) else {}
                )

                # Get results
                email_analysis = email_future.result()
                note_analysis = note_future.result()

            parallel_time = (datetime.now(timezone.utc) - parallel_start_time).total_seconds()
            self.logger.info(f"⚡ IcebreakerIntroAgent [Customer {client_id}]: PARALLEL execution completed in {parallel_time:.2f}s")
            self.logger.info(f"📊 IcebreakerIntroAgent [Customer {client_id}]: Email analysis keys: {list(email_analysis.keys()) if isinstance(email_analysis, dict) else 'Not a dict'}")
            self.logger.info(f"📊 IcebreakerIntroAgent [Customer {client_id}]: Note analysis keys: {list(note_analysis.keys()) if isinstance(note_analysis, dict) else 'Not a dict'}")

        except Exception as e:
            parallel_time = (datetime.now(timezone.utc) - parallel_start_time).total_seconds()
            self.logger.error(f"❌ IcebreakerIntroAgent [Customer {client_id}]: PARALLEL execution failed after {parallel_time:.2f}s: {str(e)}")
            import traceback
            self.logger.error(f"🔍 IcebreakerIntroAgent [Customer {client_id}]: Parallel execution traceback: {traceback.format_exc()}")
            # Set default values on failure
            email_analysis = {"error": "Parallel execution failed"}
            note_analysis = {"error": "Parallel execution failed"}

        # Fetch user preferences and feedback
        user_preferences = await self._get_user_preferences_summary(conn)
        crm_ai_insights_prefs = await self._get_crm_category_preferences(conn, 'ai_insights')
        crm_feedback_summary = await self._get_crm_feedback_summary(conn, client_id)

        # Determine Activities status based on interaction history
        activities_status = self._determine_activities_status(customer_data)

        system_message = """You are a senior client strategist preparing for a first meaningful engagement. Return exactly one valid JSON object — no markdown, no extra text.

CORE RULES:
- Be SPECIFIC: use any available data (company name, industry, contacts, prior emails/notes) to personalize
- If prior communication exists, reference it by date and content — do NOT say "no prior interactions"
- If no data exists, use industry knowledge to suggest relevant conversation starters
- Focus on giving the employee CONFIDENCE to reach out with specific talking points
- churn_risk should be "low" for new prospects

USER PREFERENCES INTEGRATION:
If USER COMMUNICATION PREFERENCES are provided, adapt your tone, formality, and focus areas accordingly.
If CRM AI INSIGHTS PREFERENCES are provided, adjust detail_level, actionability, and focus_areas to match.
If HISTORICAL FEEDBACK is provided, learn from past ratings — reinforce approaches with high ratings, adjust for low ratings."""

        prompt = f"""Analyze this customer data and return one JSON object with actionable icebreaker insights.

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
  "churn_risk": "low",
  "Insights": [
    "3 insights, each 2-3 sentences with SPECIFIC details",
    "focus on: what we know about them, what they care about, what angles to use for outreach",
    "if emails/notes exist, reference specific content as context for the conversation",
    "do NOT use fixed category labels — just state each insight directly"
  ],
  "Next Move": [
    "2-3 actions with specific outreach strategies, naming WHO to contact and WHAT to discuss"
  ]
}}}}

REQUIREMENTS:
1. Return ONLY valid JSON — no markdown, no extra text
2. Activities is pre-set as "{activities_status}"
3. Each insight: 2-3 sentences, personalized with available data
4. Write exactly 3 insights — cover company context, conversation angles, and any prior communication
5. Next steps must suggest specific outreach actions with talking points
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
                "churn_risk": "low",
                "Insights": [
                    "Momentum Assessment: Analysis processing encountered technical challenges. Manual assessment of engagement stage and prospect responsiveness recommended.",
                    "Recent Communication Analysis: Communication content analysis requires manual review to identify expressed interests, questions, and engagement patterns.",
                    "Opportunity Identification: Historical success pattern analysis needs manual processing to match prospect opportunities with relevant experience."
                ],
                "Next Move": [
                    "Review prospect communication history manually to understand engagement patterns, expressed interests, and relationship stage. Automated analysis encountered processing issues requiring human assessment to determine momentum and identify specific topics discussed.",
                    "Schedule introductory discovery call to directly understand prospect needs and establish relationship baseline. Direct engagement will provide immediate context for opportunity identification and help build initial confidence based on relevant historical successes."
                ]
            }
            return json.dumps(fallback_response, indent=2)

    def _determine_activities_status(self, customer_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """
        Determine Activities status based on interaction history

        Returns:
            "churned" if no interactions exist
            "inactive" if most recent interaction is older than 7 days
            "active" if most recent interaction is within last 7 days
        """
        # Handle different input formats
        if isinstance(customer_data, dict):
            interactions = customer_data.get("interaction_details", [])
        else:
            interactions = []

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

        # Check if within 7 days
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        if most_recent >= seven_days_ago:
            return "active"
        else:
            return "inactive"

    def _extract_call_summaries(self, customer_data: Dict[str, Any]) -> str:
        """
        Extract and format call summaries from interaction details

        Args:
            customer_data: Complete customer data structure

        Returns:
            Formatted string with call summaries or empty string
        """
        interactions = customer_data.get("interaction_details", [])
        if not interactions:
            return ""

        # Filter for call interactions
        calls = [i for i in interactions if i.get('type', '').lower() in ['call', 'phone', 'meeting']]

        if not calls:
            return ""

        # Sort by date (most recent first)
        sorted_calls = sorted(calls, key=lambda x: x.get('created_at', ''), reverse=True)

        # Format call summaries (limit to 5 most recent)
        formatted = "=== RECENT CALL SUMMARIES ===\n"
        for i, call in enumerate(sorted_calls[:5], 1):
            created_at = self._format_date_safely(call.get('created_at'))
            duration = call.get('duration_minutes', 0)
            content = call.get('content', 'No summary available')
            formatted += f"\nCall {i} ({created_at}, {duration} min):\n{content[:200]}{'...' if len(content) > 200 else ''}\n"

        return formatted

    def _format_date_safely(self, date_value) -> str:
        """
        Safely format a date value that could be a datetime object or string.

        Args:
            date_value: Could be datetime object, string, or None

        Returns:
            Formatted date string (YYYY-MM-DD) or "N/A"
        """
        if not date_value:
            return "N/A"

        try:
            if hasattr(date_value, 'strftime'):
                return date_value.strftime('%Y-%m-%d')
            elif isinstance(date_value, str):
                return date_value[:10]
            else:
                return str(date_value)[:10]
        except:
            return "N/A"

    async def analyze_customer_background(self,
                                  conn: asyncpg.Connection,
                                  customer_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """
        Analyze customer background with JSON format (same as generate_icebreaker_insights)

        Args:
            conn: asyncpg database connection
            customer_data: Customer data to analyze

        Returns:
            JSON formatted background analysis
        """
        return await self.generate_icebreaker_insights(conn, customer_data, insight_type="comprehensive")

    async def identify_conversation_starters(self,
                                     conn: asyncpg.Connection,
                                     customer_data: Union[Dict[str, Any], List[Dict[str, Any]]],
                                     conversation_type: str = "business") -> str:
        """
        Generate conversation starters with JSON format (same as generate_icebreaker_insights)

        Args:
            conn: asyncpg database connection
            customer_data: Customer data to analyze
            conversation_type: Type of conversation (parameter ignored, returns standard format)

        Returns:
            JSON formatted conversation starters
        """
        return await self.generate_icebreaker_insights(conn, customer_data, insight_type="comprehensive")

    async def assess_relationship_potential(self,
                                   conn: asyncpg.Connection,
                                   customer_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """
        Assess relationship potential with JSON format (same as generate_icebreaker_insights)

        Args:
            conn: asyncpg database connection
            customer_data: Customer data to analyze

        Returns:
            JSON formatted relationship assessment
        """
        return await self.generate_icebreaker_insights(conn, customer_data, insight_type="comprehensive")

    async def generate_value_talking_points(self,
                                    conn: asyncpg.Connection,
                                    customer_data: Union[Dict[str, Any], List[Dict[str, Any]]],
                                    focus_area: str = "comprehensive") -> str:
        """
        Generate value talking points with JSON format (same as generate_icebreaker_insights)

        Args:
            conn: asyncpg database connection
            customer_data: Customer data to analyze
            focus_area: Focus area (parameter ignored, returns standard format)

        Returns:
            JSON formatted value talking points
        """
        return await self.generate_icebreaker_insights(conn, customer_data, insight_type="comprehensive")

    async def generate_quick_insights(self, conn: asyncpg.Connection, customer_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """
        Generate quick insights with JSON format (same as generate_icebreaker_insights)

        Args:
            conn: asyncpg database connection
            customer_data: Customer data to analyze

        Returns:
            JSON formatted quick insights
        """
        return await self.generate_icebreaker_insights(conn, customer_data, insight_type="comprehensive")