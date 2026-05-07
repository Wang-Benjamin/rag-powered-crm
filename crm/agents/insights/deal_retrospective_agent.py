"""
Deal Retrospective Agent - Comprehensive Financial Value Analysis

A specialized AI agent that provides comprehensive retrospective analysis of client relationships,
combining quantitative data analysis with qualitative business insights. Emphasizes financial
value creation and interaction patterns with meaningful interpretation of what the data reveals
about business health and opportunities.

Leverages the reusable DealHistoryAgent for deal-specific analysis while adding enhanced
client-focused insights that go beyond raw statistics to provide strategic understanding.

This agent is designed for retrospective analysis with strict JSON output format,
providing comprehensive insights that combine statistical facts with business interpretation
and well-reasoned actionable recommendations.

Core Analysis Types:
1. Enhanced Financial Value Analysis (quantitative metrics + qualitative interpretation of business health)
2. Contextual Engagement Analytics (interaction data + relationship health implications)
3. Deal Pattern Analysis (from upstream DealHistoryAgent with business implications)
4. Reasoned Improvement Recommendations (actionable next steps with clear data-driven reasoning)

Enhanced Features:
- Combines quantitative statistics with qualitative business insights
- Interprets what metrics mean for relationship health and business strategy
- Provides reasoning for each recommendation based on data analysis
- Explains trends, patterns, and their business implications

Output Format:
Returns exactly one JSON object with Activities, Insights, and Next Move sections.
Each insight combines statistical data with meaningful interpretation.
Each recommendation includes clear reasoning based on the analysis.

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""

import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import asyncpg
from agents.deals.deal_history_agent import DealHistoryAgent
from agents.core.model_factory import ModelFactory

# Load environment variables from .env file
load_dotenv()

class DealRetrospectiveAgent:
    """
    Specialized AI agent for comprehensive financial value retrospective analysis.

    This agent combines deal-specific analysis (via DealHistoryAgent) with client relationship
    context to provide comprehensive retrospective insights that merge quantitative data with
    qualitative business interpretation. Returns structured JSON output with Activities status,
    enhanced Insights that combine statistics with meaning, and well-reasoned actionable
    recommendations.

    Key Features:
    - Quantitative + Qualitative Analysis: Combines statistical data with business interpretation
    - Enhanced Value Analysis: Financial metrics with trend analysis and business implications
    - Contextual Engagement Analysis: Interaction data with relationship health insights
    - Reasoned Recommendations: Each suggestion includes clear data-driven reasoning
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None,
                 email: str = None):
        """
        Initialize the Deal Retrospective Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            email: User email for database routing (optional, for consistency)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Deal Retrospective Agent",
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

        # Initialize the deal history agent for deal-specific analysis
        self.deal_history_agent = DealHistoryAgent(
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key
        )



    async def _get_user_preferences_summary(self, conn: asyncpg.Connection) -> Optional[Dict[str, Any]]:
        """
        Fetch user AI preferences summary (ai_summary column only).

        Args:
            conn: asyncpg database connection

        Returns:
            Dictionary with ai_summary data or None
        """
        if not self.email:
            return None

        try:
            from data.repositories.user_preferences_repository import UserPreferencesRepository
            prefs_repo = UserPreferencesRepository()
            return await prefs_repo.get_ai_preferences_summary(conn, self.email)
        except Exception as e:
            return None

    async def _get_crm_category_preferences(self, conn: asyncpg.Connection, category: str) -> Optional[Dict[str, Any]]:
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

    async def _get_crm_feedback_summary(self, conn: asyncpg.Connection, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch CRM feedback AI summaries for customer.
        Uses balanced approach: includes recent feedback (last 5) + highly rated feedback (rating >= 4).

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID to fetch feedback for

        Returns:
            Dictionary with 'recent' and 'highly_rated' feedback sections or None
        """
        if not self.email:
            return None

        try:
            from data.repositories.feedback_repository import FeedbackRepository
            feedback_repo = FeedbackRepository()

            # Get all feedback for customer
            feedback_list = await feedback_repo.get_feedback_by_customer(
                conn=conn,
                customer_id=customer_id,
            )

            if not feedback_list:
                return None

            # Filter feedback that has ai_summary
            feedback_with_summary = [
                f for f in feedback_list
                if f.get('ai_summary') is not None
            ]

            if not feedback_with_summary:
                return None

            # Sort by created_at (most recent first)
            sorted_feedback = sorted(
                feedback_with_summary,
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )

            # Extract recent feedback (last 5)
            recent_feedback = []
            for feedback in sorted_feedback[:5]:
                recent_feedback.append({
                    'category': feedback.get('feedback_category'),
                    'rating': feedback.get('rating'),
                    'ai_summary': feedback.get('ai_summary'),
                    'created_at': str(feedback.get('created_at', ''))
                })

            # Extract highly rated feedback (rating >= 4)
            highly_rated_feedback = []
            for feedback in sorted_feedback:
                if feedback.get('rating', 0) >= 4:
                    highly_rated_feedback.append({
                        'category': feedback.get('feedback_category'),
                        'rating': feedback.get('rating'),
                        'ai_summary': feedback.get('ai_summary'),
                        'created_at': str(feedback.get('created_at', ''))
                    })

            result = {}
            if recent_feedback:
                result['recent'] = recent_feedback
            if highly_rated_feedback:
                result['highly_rated'] = highly_rated_feedback

            return result if result else None

        except Exception as e:
            return None

    def _generate_content(self, prompt: str, system_message: str = None) -> str:
        """Generate content using the selected provider with enhanced context"""
        if system_message is None:
            system_message = "You are a senior business analyst specializing in financial value analysis and deal performance retrospectives. You provide structured JSON responses with specific insights and actionable recommendations."

        return self.model_factory.generate_content(prompt, system_message)

    def format_client_data_for_analysis(self, client_history: Dict[str, Any]) -> str:
        """
        Format client history data focusing on financial value and interactions

        Args:
            client_history: Complete client history data structure

        Returns:
            Formatted string optimized for value analysis
        """
        if not client_history:
            return "No client history data available for analysis."

        # Extract key information
        client_info = client_history.get("client_info", {})
        client_details = client_history.get("client_details", {})
        deals = client_history.get("deals", [])
        interactions = client_history.get("interaction_details", [])
        metrics = client_history.get("summary_metrics", {})

        # Calculate financial metrics
        total_deals = len(deals)
        won_deals = [d for d in deals if d.get('room_status') == 'closed-won']
        won_count = len(won_deals)
        won_value = sum(d.get('value_usd', 0) for d in won_deals)
        total_value = sum(d.get('value_usd', 0) for d in deals)
        avg_deal_value = won_value / won_count if won_count > 0 else 0
        win_rate = (won_count / total_deals * 100) if total_deals > 0 else 0

        # Calculate interaction metrics
        total_interactions = metrics.get('total_interactions', 0)
        last_interaction = 'N/A'
        if interactions:
            sorted_ints = sorted(interactions, key=lambda x: x.get('created_at', ''), reverse=True)
            last_int_date = sorted_ints[0].get('created_at')
            if last_int_date:
                last_interaction = str(last_int_date)[:10] if last_int_date else 'N/A'

        # Determine activity status
        status = client_info.get('status', 'Unknown').lower()
        if status in ['active', 'engaged']:
            activity_status = 'active'
        elif status in ['inactive', 'dormant', 'churned']:
            activity_status = 'inactive'
        else:
            activity_status = 'churned'

        formatted_data = f"""
=== CLIENT FINANCIAL ANALYSIS ===
Company: {client_info.get('name', 'N/A')}
Activity Status: {activity_status}
Total Deals: {total_deals}
Won Deals: {won_count} ({win_rate:.1f}% win rate)
Total Won Value: ${won_value:,.2f}
Average Deal Size: ${avg_deal_value:,.2f}

=== ENGAGEMENT METRICS ===
Total Interactions: {total_interactions}
Last Interaction: {last_interaction}

=== DEAL DETAILS ===
"""

        # Add individual deal information
        for i, deal in enumerate(deals, 1):
            status_emoji = "✅" if deal.get('room_status') == 'closed-won' else "❌" if deal.get('room_status') == 'closed-lost' else "🔄"
            formatted_data += f"Deal {i}: {deal.get('deal_name', 'Unnamed')} {status_emoji} - ${deal.get('value_usd', 0):,.2f}\n"

        return formatted_data

    async def generate_retrospective_analysis(self, conn: asyncpg.Connection, client_history: Dict[str, Any]) -> str:
        """
        Generate focused retrospective analysis with strict JSON output format

        This method combines deal-specific insights from DealHistoryAgent with client
        relationship context to provide structured retrospective insights focused on
        financial value, engagement, and actionable improvements.

        Args:
            client_history: Complete client history data

        Returns:
            JSON string with Activities, Insights (3 items), and Next Move sections
        """
        # Get formatted data for analysis
        formatted_data = self.format_client_data_for_analysis(client_history)

        # Get deal pattern insights from DealHistoryAgent
        deal_patterns = ""
        if client_history.get("deals"):
            try:
                deal_patterns = self.deal_history_agent.generate_deal_insights(
                    client_history,
                    insight_type="quick"
                )
            except Exception as e:
                deal_patterns = f"Deal analysis error: {str(e)}"

        # Get user preferences summary
        user_preferences = await self._get_user_preferences_summary(conn)

        # Get CRM category preferences for deal insights
        crm_deal_insights_prefs = await self._get_crm_category_preferences(conn, 'deal_insights')

        # Get CRM feedback summary for this customer
        client_id = client_history.get("client_info", {}).get("client_id")
        crm_feedback_summary = await self._get_crm_feedback_summary(conn, client_id) if client_id else None

        system_message = """You are a senior business analyst specializing in comprehensive client retrospective analysis. You excel at combining quantitative data analysis with qualitative business insights. You must return exactly one JSON object with the specified structure, providing both statistical facts and meaningful interpretation of what those numbers mean for business strategy, relationship health, and future opportunities. Your analysis should demonstrate deep understanding of how financial metrics and engagement patterns interconnect to reveal the true state of client relationships.

CRITICAL: For DealRetrospectiveAgent analysis, the customer status is always "completed" (clients with interactions but no active deals - completed engagement cycle) and churn_risk is always "low" (they have engagement history indicating relationship potential).

CRITICAL REQUIREMENT - USER PREFERENCES INTEGRATION:
If USER COMMUNICATION PREFERENCES are provided, you MUST incorporate them into your response generation:
- communication_style: Adapt your tone, formality, conciseness, and proactiveness to match user preferences
- boundaries_restrictions: Strictly avoid restricted topics and follow all specified guardrails
- target_audience_focus: Tailor recommendations to the user's target audience and ideal customer profile
- key_recommendations: Incorporate user-specific best practices into your strategic recommendations

CRITICAL REQUIREMENT - HISTORICAL FEEDBACK INTEGRATION:
If HISTORICAL CRM FEEDBACK is provided, you MUST learn from past feedback patterns:

RECENT FEEDBACK (last 5 entries):
- Shows current user preferences and recent trends
- Identify what approaches are working NOW
- Adapt to any shifts in communication style or priorities

HIGHLY RATED FEEDBACK (rating >= 4):
- Shows proven best practices that the user valued most
- Identify consistent patterns in successful interactions
- Prioritize approaches that received high ratings historically

INTEGRATION STRATEGY:
- If recent feedback conflicts with highly rated feedback, prioritize RECENT (shows evolution)
- If both align, strongly emphasize those approaches
- If specific categories have consistently high/low ratings, adjust recommendations accordingly
- Use feedback to calibrate your confidence level in recommendations

CRITICAL REQUIREMENT - CRM DEAL INSIGHTS PREFERENCES:
If CRM DEAL INSIGHTS PREFERENCES are provided, you MUST adapt your output based on learned user preferences:
- detail_level: Adjust insight depth (brief/moderate/detailed) to match user preference
- tone: Match the preferred communication tone (formal/casual/professional)
- actionability: Emphasize actionable recommendations if user prefers high actionability
- focus_areas: Prioritize insights in the user's preferred focus areas (e.g., deal value, timeline, risk)
- metrics_preference: Include/exclude specific deal metrics based on user preference
- preference_summary: Use this as a guide for overall output style
These preferences are learned from user feedback and should significantly influence your response.

When preferences or feedback are unavailable, use general best practices."""

        prompt = f"""Analyze this client relationship data and return exactly one JSON object with comprehensive quantitative and qualitative analysis:

{formatted_data}

DEAL PATTERN ANALYSIS:
{deal_patterns}

=== USER COMMUNICATION PREFERENCES ===
{json.dumps(user_preferences, indent=2) if user_preferences else "No user preferences configured"}

=== CRM DEAL INSIGHTS PREFERENCES ===
{json.dumps(crm_deal_insights_prefs, indent=2) if crm_deal_insights_prefs else "No CRM deal insights preferences configured"}

=== HISTORICAL CRM FEEDBACK ===
{json.dumps(crm_feedback_summary, indent=2) if crm_feedback_summary else "No historical feedback available"}

OUTPUT CONTRACT (strict):
Return exactly one JSON object:
{{
  "Activities": "completed",
  "churn_risk": "low",
  "Insights": [
    "Value: ...",                  // Enhanced analysis combining quantitative stats with qualitative interpretation
    "Engagement: ...",             // Enhanced analysis combining quantitative data with qualitative context
    "Deal pattern: ...",           // Enhanced analysis from upstream patterns with business implications
  ],
  "Next Move": [
    "Recommendation 1: [Action] - [Clear reasoning based on data analysis]",
    "Recommendation 2: [Action] - [Clear reasoning based on data analysis]",
    "Recommendation 3: [Action] - [Clear reasoning based on data analysis]"
  ]
}}

ENHANCED ANALYSIS REQUIREMENTS:

VALUE SECTION:
- Include quantitative statistics: total won value, deal count, win rate, average deal size
- Add qualitative analysis: interpret what these numbers mean for business health, revenue trends, deal size evolution
- Provide insights about value patterns: growth trajectory, deal velocity, revenue concentration
- Explain business implications: what the financial performance indicates about client relationship strength

ENGAGEMENT SECTION:
- Include quantitative data: interaction counts, frequency, recency
- Add qualitative analysis: what engagement patterns reveal about relationship health
- Contextualize engagement levels: high/low engagement implications for business
- Explain relationship indicators: what interaction patterns suggest about client commitment

NEXT MOVE SECTION:
- For each recommendation, provide clear reasoning that connects back to the analysis
- Explain why each action is relevant based on specific data insights
- Link recommendations to value or engagement findings
- Ensure reasoning demonstrates understanding of the client's situation and needs

Requirements:
- Activities must be one of: "active", "inactive", "completed", "churned"
- Insights must be exactly 3 items starting with "Value:", "Engagement:", "Deal pattern:"
- Each insight should combine quantitative data with meaningful qualitative interpretation
- Next Move must be 2-3 actionable recommendations with clear reasoning statements
- Use actual data from the analysis to support all insights and recommendations
"""

        return self._generate_content(prompt, system_message)

    async def generate_quick_insights(self, conn: asyncpg.Connection, client_history: Dict[str, Any]) -> str:
        """
        Generate quick key insights with JSON format

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data

        Returns:
            JSON formatted insights summary
        """
        return await self.generate_retrospective_analysis(conn, client_history)

    # Backward compatibility methods
    def format_client_history_for_llm(self, client_history: Dict[str, Any]) -> str:
        """
        Backward compatibility method - redirects to the new data formatting

        Args:
            client_history: Complete client history data structure

        Returns:
            Formatted string ready for LLM processing
        """
        return self.format_client_data_for_analysis(client_history)

    async def generate_comprehensive_summary(self, conn: asyncpg.Connection, client_history: Dict[str, Any]) -> str:
        """
        Backward compatibility method - redirects to the new retrospective analysis

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data

        Returns:
            JSON formatted retrospective analysis
        """
        return await self.generate_retrospective_analysis(conn, client_history)

    def format_client_history_for_retrospective(self, client_history: Dict[str, Any]) -> str:
        """
        Backward compatibility method - redirects to the new data formatting

        Args:
            client_history: Complete client history data structure

        Returns:
            Formatted string ready for analysis
        """
        return self.format_client_data_for_analysis(client_history)

    async def generate_comprehensive_retrospective(self, conn: asyncpg.Connection, client_history: Dict[str, Any]) -> str:
        """
        Backward compatibility method - redirects to the new retrospective analysis

        Args:
            conn: asyncpg database connection
            client_history: Complete client history data

        Returns:
            JSON formatted retrospective analysis
        """
        return await self.generate_retrospective_analysis(conn, client_history)
