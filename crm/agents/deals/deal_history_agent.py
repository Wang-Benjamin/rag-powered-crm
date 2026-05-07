"""
Deal History Agent - Reusable AI Analysis Engine with Structured Output

A flexible, reusable AI agent that provides intelligent analysis of deal histories using
multiple LLM providers (Google Gemini and OpenAI). This agent is designed to be used as
a common component by other specialized agents.

Key Features:
1. Variable input support - can analyze any number of deal records
2. Structured output format with required sections
3. Multi-provider AI support (Gemini, OpenAI)
4. Consistent formatting with total value, deal count, descriptions, and insights
5. Enhanced prompt engineering for better accuracy

Core Analysis Capabilities:
- Deal performance analysis with structured output
- Pattern recognition across multiple deals
- Trend identification with quantitative metrics
- Risk assessment with specific indicators
- Opportunity identification with actionable insights
- Strategic insights generation with required format

Required Output Format:
All analysis methods return structured output including:
- DEAL SUMMARY: Total Value, Number of Deals, Won Value
- DEAL DESCRIPTIONS: Each deal with name, value, stage, description
- INSIGHTS/ANALYSIS: Specific analysis based on method type

Supported Providers:
- Google Gemini (gemini-1.5-flash, gemini-1.5-pro)
- OpenAI (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
"""

import os
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
from agents.core.model_factory import ModelFactory

# Load environment variables from .env file
load_dotenv()


class DealHistoryAgent:
    """
    Reusable AI-powered Deal History Analysis Agent
    
    This agent provides flexible deal analysis capabilities that can be used by other
    specialized agents. It accepts variable numbers of deal records and provides
    structured analysis based on the specific use case requirements.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None):
        """
        Initialize the Deal History Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Deal History Agent",
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key
        )

        # Get model info for backward compatibility
        model_info = self.model_factory.get_model_info()
        self.provider = model_info.provider
        self.model_name = model_info.model_name
        self.client = model_info.client  # For OpenAI

    def _generate_content(self, prompt: str, system_message: str = None) -> str:
        """
        Generate content using the selected provider with enhanced error handling

        Args:
            prompt: The user prompt
            system_message: Optional system message for better context
        """
        if system_message is None:
            system_message = "You are a senior business analyst and deal strategist with expertise in analyzing deal patterns, identifying trends, and providing actionable insights. You must follow the specified output format exactly, including total value, number of deals, each deal description, and generated insights."

        return self.model_factory.generate_content(prompt, system_message)

    def format_deals_for_analysis(self, 
                                  deals_data: Union[List[Dict[str, Any]], Dict[str, Any]], 
                                  context: str = "general",
                                  include_summary_stats: bool = True) -> str:
        """
        Format deal data for LLM analysis with flexible input support
        
        Args:
            deals_data: Either a list of deal records or a complete client history dict
            context: Analysis context ("general", "retrospective", "comparison", etc.)
            include_summary_stats: Whether to include calculated summary statistics
            
        Returns:
            Formatted string ready for LLM processing
        """
        if not deals_data:
            return "No deal data available for analysis."

        # Handle different input formats
        if isinstance(deals_data, dict):
            # Complete client history format
            deals = deals_data.get("deals", [])
            client_info = deals_data.get("client_info", {})
            metrics = deals_data.get("summary_metrics", {})
            has_client_context = True
        else:
            # List of deals format
            deals = deals_data if isinstance(deals_data, list) else [deals_data]
            client_info = {}
            metrics = {}
            has_client_context = False

        if not deals:
            return "No deals found in the provided data."

        # Build formatted output
        formatted_data = f"=== DEAL ANALYSIS CONTEXT: {context.upper()} ===\n"
        
        if has_client_context and client_info:
            formatted_data += f"""
=== CLIENT CONTEXT ===
Company: {client_info.get('name', 'N/A')}
Status: {client_info.get('status', 'N/A')}
"""

        # Calculate summary statistics if requested
        if include_summary_stats:
            total_deals = len(deals)
            won_deals = len([d for d in deals if d.get('room_status') == 'closed-won'])
            lost_deals = len([d for d in deals if d.get('room_status') == 'closed-lost'])
            in_progress_deals = total_deals - won_deals - lost_deals
            
            total_value = sum(d.get('value_usd', 0) for d in deals)
            won_value = sum(d.get('value_usd', 0) for d in deals if d.get('room_status') == 'closed-won')
            avg_deal_value = total_value / total_deals if total_deals > 0 else 0
            win_rate = (won_deals / total_deals * 100) if total_deals > 0 else 0

            formatted_data += f"""
=== DEAL PORTFOLIO SUMMARY ===
Total Deals: {total_deals}
Won Deals: {won_deals} ({win_rate:.1f}% win rate)
Lost Deals: {lost_deals}
In Progress: {in_progress_deals}
Total Portfolio Value: ${total_value:,.2f}
Won Deal Value: ${won_value:,.2f}
Average Deal Size: ${avg_deal_value:,.2f}
"""

        formatted_data += "\n=== INDIVIDUAL DEAL DETAILS ===\n"
        
        # Sort deals by value (descending) for better analysis
        sorted_deals = sorted(deals, key=lambda x: x.get('value_usd', 0), reverse=True)
        
        for i, deal in enumerate(sorted_deals, 1):
            status_emoji = "✅" if deal.get('room_status') == 'closed-won' else "❌" if deal.get('room_status') == 'closed-lost' else "🔄"
            
            formatted_data += f"""
Deal #{i}: {deal.get('deal_name', 'Unnamed Deal')} {status_emoji}
  Value: ${deal.get('value_usd', 0):,.2f}
  Room Status: {deal.get('room_status', 'Unknown')}
  Description: {deal.get('description', 'No description')[:100]}{'...' if len(deal.get('description', '')) > 100 else ''}
  Created: {deal.get('created_at', 'N/A')}
  Expected Close: {deal.get('expected_close_date', 'N/A')}
"""

        return formatted_data

    def _extract_deal_metrics(self, deals_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract key deal metrics for structured output

        Args:
            deals_data: Deal data to analyze

        Returns:
            Dictionary with total_deals, total_value, won_deals, won_value
        """
        if isinstance(deals_data, dict):
            deals = deals_data.get("deals", [])
        else:
            deals = deals_data if isinstance(deals_data, list) else [deals_data]

        total_deals = len(deals)
        total_value = sum(d.get('value_usd', 0) for d in deals)
        won_deals = [d for d in deals if d.get('room_status') == 'closed-won']
        won_count = len(won_deals)
        won_value = sum(d.get('value_usd', 0) for d in won_deals)

        return {
            'deals': deals,
            'total_deals': total_deals,
            'total_value': total_value,
            'won_count': won_count,
            'won_value': won_value,
            'win_rate': (won_count / total_deals * 100) if total_deals > 0 else 0
        }

    def analyze_deal_patterns(self,
                             deals_data: Union[List[Dict[str, Any]], Dict[str, Any]],
                             analysis_focus: str = "comprehensive") -> str:
        """
        Analyze patterns across multiple deals with structured output format

        Args:
            deals_data: Deal data to analyze
            analysis_focus: Focus area ("comprehensive", "performance", "trends", "risks")

        Returns:
            Structured pattern analysis with required format
        """
        # Extract deal metrics for structured output
        metrics = self._extract_deal_metrics(deals_data)

        formatted_data = self.format_deals_for_analysis(deals_data, context="pattern_analysis")

        focus_prompts = {
            "comprehensive": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== COMPREHENSIVE PATTERN ANALYSIS ===
1. **PERFORMANCE PATTERNS** - Success rates, value trends, timing patterns
2. **DEAL CHARACTERISTICS** - Common features of successful vs unsuccessful deals
3. **TREND ANALYSIS** - Temporal trends, seasonal patterns, progression over time
4. **RISK INDICATORS** - Warning signs and risk factors identified
5. **STRATEGIC INSIGHTS** - Key learnings and strategic recommendations""",

            "performance": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== PERFORMANCE PATTERN ANALYSIS ===
1. **WIN/LOSS ANALYSIS** - What differentiates successful deals?
2. **VALUE PATTERNS** - Deal size impact on success rates
3. **TIMING ANALYSIS** - How deal duration affects outcomes
4. **PERFORMANCE METRICS** - Key performance indicators and benchmarks""",

            "trends": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== TREND ANALYSIS ===
1. **TEMPORAL TRENDS** - How performance changes over time
2. **SEASONAL PATTERNS** - Cyclical behaviors and seasonal effects
3. **PROGRESSION ANALYSIS** - Deal pipeline evolution
4. **FORECASTING INSIGHTS** - Predictive indicators for future performance""",

            "risks": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== RISK ANALYSIS ===
1. **RISK FACTORS** - Common characteristics of failed deals
2. **WARNING SIGNS** - Early indicators of potential problems
3. **MITIGATION STRATEGIES** - How to address identified risks
4. **PREVENTION MEASURES** - Proactive steps to avoid future failures"""
        }

        system_message = f"""You are an expert deal analyst. You MUST follow the exact output format specified. Always include:
1. DEAL SUMMARY section with Total Value: ${metrics['total_value']:,.2f}, Number of Deals: {metrics['total_deals']}, Won Value: ${metrics['won_value']:,.2f}
2. DEAL DESCRIPTIONS section listing each deal with name, value, stage, and description
3. Analysis section with the requested focus area

Use the actual numbers provided and format currency values properly."""

        prompt = f"""Analyze the following deal portfolio data using the specified format:

{formatted_data}

{focus_prompts.get(analysis_focus, focus_prompts['comprehensive'])}

IMPORTANT: You must include the exact sections specified above. Use concrete examples from the deals when making points. Focus on patterns that can inform future deal strategy and execution."""

        return self._generate_content(prompt, system_message)

    def generate_deal_insights(self,
                              deals_data: Union[List[Dict[str, Any]], Dict[str, Any]],
                              insight_type: str = "strategic") -> str:
        """
        Generate specific insights from deal data with structured output format

        Args:
            deals_data: Deal data to analyze
            insight_type: Type of insights ("strategic", "tactical", "quick", "detailed")

        Returns:
            Structured insights with required format: total value, number of deals, descriptions, insights
        """
        # Extract deal metrics for structured output
        metrics = self._extract_deal_metrics(deals_data)

        formatted_data = self.format_deals_for_analysis(deals_data, context="insights_generation")

        insight_prompts = {
            "strategic": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== STRATEGIC INSIGHTS ===
• 3 Key Strategic Opportunities identified from the deal patterns
• 3 Major Strategic Risks that need attention
• 3 Strategic Recommendations for improving deal performance
• Overall Portfolio Health Score (1-10) with justification""",

            "tactical": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and brief description]

=== TACTICAL INSIGHTS ===
• 3 Tactical improvements for deal closing
• 3 Process optimizations based on successful deals
• 3 Immediate action items for current deals
• Resource allocation recommendations""",

            "quick": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage]

=== QUICK INSIGHTS ===
• Top 3 Deal Performance Drivers
• Top 3 Risk Factors to Monitor
• Top 3 Immediate Actions Required""",

            "detailed": """REQUIRED OUTPUT FORMAT:
=== DEAL SUMMARY ===
Total Value: $[total_value]
Number of Deals: [number]
Won Value: $[won_value]

=== DEAL DESCRIPTIONS ===
[List each deal with name, value, stage, and detailed description]

=== DETAILED INSIGHTS ===
1. **PERFORMANCE ANALYSIS** - Detailed breakdown of what's working
2. **GAP ANALYSIS** - Where improvements are needed
3. **COMPETITIVE POSITIONING** - How deals compare to benchmarks
4. **RESOURCE OPTIMIZATION** - How to better allocate resources
5. **FUTURE OUTLOOK** - Predictions and recommendations"""
        }

        system_message = f"""You are a senior business analyst. You MUST follow the exact output format specified. Always include:
1. DEAL SUMMARY section with Total Value: ${metrics['total_value']:,.2f}, Number of Deals: {metrics['total_deals']}, Won Value: ${metrics['won_value']:,.2f}
2. DEAL DESCRIPTIONS section listing each deal
3. INSIGHTS section with the requested analysis type

Use the actual numbers provided and format currency values properly."""

        prompt = f"""Analyze the following deal data using the specified format:

{formatted_data}

{insight_prompts.get(insight_type, insight_prompts['strategic'])}

IMPORTANT: You must include the exact sections specified above. Use the actual deal data provided to populate the DEAL DESCRIPTIONS section."""

        return self._generate_content(prompt, system_message)

    def compare_deal_performance(self,
                                deals_data: Union[List[Dict[str, Any]], Dict[str, Any]],
                                comparison_criteria: str = "stage") -> str:
        """
        Compare deal performance across different criteria

        Args:
            deals_data: Deal data to analyze
            comparison_criteria: Criteria for comparison ("stage", "value", "timeline", "custom")

        Returns:
            Comparative analysis of deal performance
        """
        formatted_data = self.format_deals_for_analysis(deals_data, context="performance_comparison")

        comparison_prompts = {
            "stage": """Compare deals by their current stage and provide:
1. **STAGE-BY-STAGE ANALYSIS** - Performance metrics for each deal stage
2. **CONVERSION RATES** - Success rates between stages
3. **BOTTLENECKS** - Where deals get stuck most often
4. **OPTIMIZATION OPPORTUNITIES** - How to improve stage progression""",

            "value": """Compare deals by value tiers and provide:
1. **VALUE TIER ANALYSIS** - Performance by deal size categories
2. **SIZE-SUCCESS CORRELATION** - How deal size affects win rates
3. **RESOURCE ALLOCATION** - Optimal resource distribution by deal size
4. **VALUE OPTIMIZATION** - Strategies for different deal sizes""",

            "timeline": """Compare deals by timeline characteristics and provide:
1. **TIMELINE ANALYSIS** - Performance by deal duration
2. **VELOCITY PATTERNS** - Fast vs slow-moving deals
3. **TIMING OPTIMIZATION** - Optimal deal timing strategies
4. **ACCELERATION OPPORTUNITIES** - How to speed up deal closure""",

            "custom": """Provide a comprehensive comparative analysis covering:
1. **MULTI-DIMENSIONAL COMPARISON** - Performance across multiple criteria
2. **CORRELATION ANALYSIS** - Relationships between different factors
3. **SEGMENTATION INSIGHTS** - Natural groupings and their characteristics
4. **OPTIMIZATION MATRIX** - Prioritized improvement opportunities"""
        }

        prompt = f"""Perform a comparative analysis of the following deals based on {comparison_criteria} and {comparison_prompts.get(comparison_criteria, comparison_prompts['custom'])}

{formatted_data}

Provide specific recommendations for each segment or category identified. Use data from the deals to support your analysis and recommendations."""

        return self._generate_content(prompt)

    def identify_success_factors(self,
                                deals_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> str:
        """
        Identify key success factors from deal data

        Args:
            deals_data: Deal data to analyze

        Returns:
            Analysis of key success factors
        """
        formatted_data = self.format_deals_for_analysis(deals_data, context="success_factor_analysis")

        system_message = """You are a deal success expert who specializes in identifying the key factors that differentiate successful deals from unsuccessful ones. Your analysis should be practical and actionable."""

        prompt = f"""Analyze the following deal data to identify key success factors:

{formatted_data}

Provide a detailed analysis covering:

1. **SUCCESS FACTOR IDENTIFICATION**
   - What characteristics do successful deals share?
   - What patterns emerge from won vs lost deals?
   - Which factors have the strongest correlation with success?

2. **FAILURE PATTERN ANALYSIS**
   - What common factors appear in lost deals?
   - What warning signs should be monitored?
   - Which risk factors are most predictive of failure?

3. **ACTIONABLE RECOMMENDATIONS**
   - How can these success factors be replicated?
   - What processes should be implemented?
   - How can failure patterns be avoided?

4. **SUCCESS METRICS & KPIs**
   - What metrics best predict deal success?
   - Which KPIs should be tracked going forward?
   - How should success be measured and monitored?

Focus on practical, implementable insights that can improve future deal performance."""

        return self._generate_content(prompt, system_message)
