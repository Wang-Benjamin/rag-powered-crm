"""
Feedback Analysis Agent for CRM Feedback System

This agent analyzes feedback history and generates AI-powered summaries
that synthesize patterns, sentiment trends, and actionable insights.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from agents.core.model_factory import ModelFactory

logger = logging.getLogger(__name__)


class FeedbackAnalysisAgent:
    """Agent for analyzing feedback history and generating AI summaries."""

    def __init__(self,
                 provider: str = "openai",
                 model_name: Optional[str] = None,
                 openai_api_key: Optional[str] = None):
        """
        Initialize the feedback analysis agent.

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses DEFAULT_OPENAI_MODEL from .env)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Feedback Analysis Agent",
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key
        )

        self.max_tokens = 500
        self.temperature = 0.3  # Lower temperature for more consistent analysis

    def calculate_entry_weight(self, index: int, total: int) -> float:
        """
        Calculate weight for feedback entry based on recency.
        Most recent entries get higher weight.
        
        Args:
            index: Position in the list (0 = most recent)
            total: Total number of entries
            
        Returns:
            Weight value between 0 and 1
        """
        if total == 1:
            return 1.0
        
        # Exponential decay: most recent = 1.0, older entries decay
        decay_factor = 0.6
        return decay_factor ** index

    def analyze_feedback_history(
        self,
        feedback_history: List[Dict[str, Any]],
        current_rating: int,
        feedback_category: str,
        customer_id: int,
        deal_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze feedback history and generate AI summary.
        
        Args:
            feedback_history: List of feedback entries (newest first expected)
            current_rating: Current/latest rating
            feedback_category: Category of feedback
            customer_id: Customer ID for context
            deal_id: Optional deal ID for context
            
        Returns:
            AI summary dict or None if analysis fails
        """
        try:
            # Validate input
            if not feedback_history or len(feedback_history) == 0:
                logger.info("No feedback history to analyze")
                return None

            # Reverse to get newest first (if not already)
            # Assume feedback_history is in chronological order (oldest first)
            sorted_history = sorted(
                feedback_history,
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )

            # Extract ratings for trend analysis
            ratings = [current_rating]  # Start with current
            for entry in sorted_history[1:]:  # Skip first (it's the current one)
                # Try to infer rating from context if available
                pass

            # Build weighted feedback entries for prompt
            weighted_entries = []
            for idx, entry in enumerate(sorted_history[:5]):  # Analyze up to 5 most recent
                weight = self.calculate_entry_weight(idx, min(len(sorted_history), 5))
                weighted_entries.append({
                    'text': entry.get('text', ''),
                    'timestamp': entry.get('timestamp', ''),
                    'weight': weight,
                    'position': idx + 1
                })

            # Generate prompt
            prompt = self._build_analysis_prompt(
                feedback_category=feedback_category,
                weighted_entries=weighted_entries,
                current_rating=current_rating,
                entity_type='deal' if deal_id else 'customer'
            )

            # Call LLM using ModelFactory
            logger.info(f"Calling LLM for feedback analysis (category: {feedback_category}, entries: {len(weighted_entries)})")
            system_message = "You are a feedback analysis expert. Analyze employee feedback and provide structured insights in JSON format."

            content = self.model_factory.generate_content(prompt, system_message)

            if not content or content.startswith("Error generating content"):
                logger.warning(f"LLM call failed: {content}")
                return self._generate_fallback_summary(weighted_entries, current_rating)

            content = content.strip()
            
            # Try to extract JSON from response
            ai_summary = self._parse_llm_response(content)
            
            if ai_summary:
                # Add metadata
                ai_summary['generated_at'] = datetime.now(timezone.utc).isoformat()
                ai_summary['entries_analyzed'] = len(weighted_entries)
                logger.info(f"✅ Successfully generated AI summary for {feedback_category}")
                return ai_summary
            else:
                logger.warning("Failed to parse LLM response, using fallback")
                return self._generate_fallback_summary(weighted_entries, current_rating)

        except Exception as e:
            logger.error(f"Error in feedback analysis: {e}", exc_info=True)
            # Return fallback summary
            return self._generate_fallback_summary(
                weighted_entries if 'weighted_entries' in locals() else [],
                current_rating
            )

    def _build_analysis_prompt(
        self,
        feedback_category: str,
        weighted_entries: List[Dict],
        current_rating: int,
        entity_type: str
    ) -> str:
        """Build the LLM prompt for feedback analysis."""
        
        # Format feedback entries
        entries_text = []
        for entry in weighted_entries:
            timestamp = entry['timestamp']
            text = entry['text'] or '(no text provided)'
            weight = entry['weight']
            entries_text.append(
                f"Entry {entry['position']} (weight: {weight:.2f}, time: {timestamp}):\n{text}"
            )
        
        entries_formatted = "\n\n".join(entries_text)
        
        # Map category to human-readable name
        category_names = {
            'churn_risk': 'Churn Risk Prediction',
            'ai_insights': 'AI Insights Quality',
            'stage_progression': 'Deal Stage Progression',
            'deal_insights': 'Deal Insights Quality'
        }
        category_display = category_names.get(feedback_category, feedback_category)
        
        prompt = f"""You are analyzing employee feedback for a CRM system feature: {category_display}.

Entity Type: {entity_type}
Current Rating: {current_rating}/5 stars
Total Feedback Entries: {len(weighted_entries)}

Feedback History (newest first, with recency weights):
{entries_formatted}

Analyze this feedback and provide:
1. A concise summary (2-4 sentences) synthesizing how the feedback has evolved over time
2. Rating trend: "improving", "declining", or "stable"
3. Sentiment evolution: "positive", "negative", or "mixed"
4. Key recurring themes (max 3 themes)
5. Actionable insights for improvement (max 2 insights)

IMPORTANT: Give more weight to recent entries (higher weight values) while still considering historical context.

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "summary": "Your 2-4 sentence summary here",
  "rating_trend": "improving|declining|stable",
  "sentiment_evolution": "positive|negative|mixed",
  "key_themes": ["theme1", "theme2", "theme3"],
  "actionable_insights": ["insight1", "insight2"]
}}"""
        
        return prompt

    def _parse_llm_response(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response and extract JSON.
        
        Args:
            content: Raw LLM response
            
        Returns:
            Parsed JSON dict or None
        """
        try:
            # Try direct JSON parse
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object in text
            if '{' in content and '}' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"Could not parse LLM response as JSON: {content[:200]}")
            return None

    def _generate_fallback_summary(
        self,
        weighted_entries: List[Dict],
        current_rating: int
    ) -> Dict[str, Any]:
        """
        Generate a basic fallback summary when LLM fails.
        
        Args:
            weighted_entries: Weighted feedback entries
            current_rating: Current rating
            
        Returns:
            Basic summary dict
        """
        entry_count = len(weighted_entries)
        
        # Basic sentiment based on rating
        if current_rating >= 4:
            sentiment = "positive"
            summary = f"Feedback is generally positive with a {current_rating}/5 rating."
        elif current_rating >= 3:
            sentiment = "mixed"
            summary = f"Feedback is mixed with a {current_rating}/5 rating."
        else:
            sentiment = "negative"
            summary = f"Feedback indicates concerns with a {current_rating}/5 rating."
        
        if entry_count > 1:
            summary += f" Based on {entry_count} feedback entries."
        
        return {
            "summary": summary,
            "rating_trend": "stable",
            "sentiment_evolution": sentiment,
            "key_themes": ["Rating-based analysis (LLM unavailable)"],
            "actionable_insights": ["Review detailed feedback for specific improvements"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entries_analyzed": entry_count,
            "fallback": True
        }

