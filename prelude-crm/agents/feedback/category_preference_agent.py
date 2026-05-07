"""
Category Preference Agent
Extracts user preferences from feedback using LLM
"""

import logging
import math
from typing import Dict, Any, Optional
from agents.core.model_factory import ModelFactory
from service_core.llm_json import extract_json

logger = logging.getLogger(__name__)


class CategoryPreferenceAgent:
    """Agent for extracting category preferences from feedback."""

    def __init__(self, provider: str = "openai", model_name: Optional[str] = None):
        """
        Initialize with ModelFactory (same pattern as FeedbackAnalysisAgent).

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses DEFAULT_OPENAI_MODEL from .env)
        """
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Category Preference Agent",
            provider=provider,
            model_name=model_name
        )
        self.temperature = 0.3  # Lower temperature for consistent extraction

    def extract_preferences_from_feedback(
        self,
        feedback_text: str,
        rating: int,
        category: str,
        existing_preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract preference updates from feedback.

        Args:
            feedback_text: User's feedback text
            rating: 1-5 star rating
            category: Feedback category ('churn_risk', 'ai_insights', etc.)
            existing_preferences: Current preferences for this category

        Returns:
            Extracted preferences dict containing:
            - detail_level: str
            - tone: str
            - actionability: str
            - focus_areas: list
            - metrics_preference: list
            - category_specific: dict
            - preference_summary: str
            - confidence: float (0.0-1.0)
            - reasoning: str
        """
        try:
            prompt = self._build_extraction_prompt(
                feedback_text, rating, category, existing_preferences
            )

            system_message = (
                "You are an expert at analyzing user feedback and extracting "
                "preferences for AI-generated content. Return only valid JSON."
            )

            content = self.model_factory.generate_content(prompt, system_message)

            if not content or content.startswith("Error"):
                logger.warning(f"LLM extraction failed: {content}")
                return self._generate_fallback_preferences(rating, category)

            # Parse LLM response
            extracted = self._parse_llm_response(content)

            if extracted:
                logger.info(f"✅ Extracted preferences for {category}")
                return extracted
            else:
                logger.warning("Failed to parse LLM response, using fallback")
                return self._generate_fallback_preferences(rating, category)

        except Exception as e:
            logger.error(f"Error extracting preferences: {e}", exc_info=True)
            return self._generate_fallback_preferences(rating, category)

    def _build_extraction_prompt(
        self, feedback_text: str, rating: int, category: str, existing: Optional[Dict]
    ) -> str:
        """Build LLM prompt for preference extraction."""

        # Category-specific context
        category_contexts = {
            'churn_risk': {
                'desc': 'customer churn risk predictions and health analysis',
                'focus': ['engagement metrics', 'response patterns', 'meeting frequency', 'contract status'],
                'metrics': ['email_response_rate', 'days_since_contact', 'engagement_score', 'sentiment_trend']
            },
            'ai_insights': {
                'desc': 'general AI insights about customer behavior and needs',
                'focus': ['pain points', 'buying signals', 'decision factors', 'objections'],
                'metrics': ['sentiment_score', 'interest_level', 'conversation_topics', 'readiness']
            },
            'stage_progression': {
                'desc': 'deal stage progression predictions',
                'focus': ['timeline estimates', 'blockers', 'confidence levels', 'historical patterns'],
                'metrics': ['days_in_stage', 'win_probability', 'similar_deal_velocity', 'next_milestone']
            },
            'deal_insights': {
                'desc': 'deal-specific insights and analysis',
                'focus': ['stakeholder mapping', 'competitive analysis', 'risk factors', 'value proposition'],
                'metrics': ['deal_size', 'discount_level', 'stakeholder_count', 'competitor_count']
            }
        }

        ctx = category_contexts.get(category, category_contexts['ai_insights'])

        # Format existing preferences
        existing_text = "No existing preferences (first feedback)" if not existing else f"""
Current Preferences ({existing.get('feedback_count', 0)} feedbacks):
- Detail: {existing.get('detail_level', 'not set')}
- Tone: {existing.get('tone', 'not set')}
- Actionability: {existing.get('actionability', 'not set')}
- Focus: {', '.join(existing.get('focus_areas', [])) or 'none'}
- Summary: {existing.get('preference_summary', 'none')}"""

        return f"""Analyze user feedback for {ctx['desc']}.

Feedback:
- Rating: {rating}/5 stars
- Text: "{feedback_text or '(no text)'}"

{existing_text}

Common focus areas: {', '.join(ctx['focus'])}
Common metrics: {', '.join(ctx['metrics'])}

Guidelines:
- High rating (4-5): User likes current approach, reinforce preferences
- Low rating (1-2): User dislikes approach, shift preferences
  * "too much detail" → detail_level: "concise"
  * "too vague" → detail_level: "comprehensive"
  * "need action steps" → actionability: "immediate_actions"
  * "just analysis" → actionability: "observational"
  * "too robotic" → tone: "conversational"
  * "show data" → tone: "data-driven"
- Mid rating (3): Small adjustments based on text

Extract:
- detail_level: concise | medium | comprehensive
- tone: data-driven | conversational | formal
- actionability: immediate_actions | strategic_guidance | observational
- focus_areas: list of topics mentioned (max 5)
- metrics_preference: list of metrics mentioned (max 5)

Return ONLY valid JSON (no markdown):
{{
  "detail_level": "concise|medium|comprehensive",
  "tone": "data-driven|conversational|formal",
  "actionability": "immediate_actions|strategic_guidance|observational",
  "focus_areas": ["area1", "area2"],
  "metrics_preference": ["metric1"],
  "category_specific": {{}},
  "preference_summary": "1-2 sentence summary",
  "confidence": 0.0-1.0,
  "reasoning": "why these preferences were inferred"
}}"""

    def _parse_llm_response(self, content: str) -> Optional[Dict]:
        """Parse LLM JSON response."""
        parsed = extract_json(content)
        if isinstance(parsed, dict):
            return parsed
        logger.warning(f"Could not parse LLM response as JSON: {content[:200]}")
        return None

    def _generate_fallback_preferences(self, rating: int, category: str) -> Dict:
        """Generate basic preferences when LLM fails."""
        # Simple heuristic based on rating
        if rating >= 4:
            detail = "medium"
            sentiment = "User seems satisfied"
        elif rating <= 2:
            detail = "concise"
            sentiment = "User wants improvements"
        else:
            detail = "medium"
            sentiment = "User has mixed feelings"

        return {
            "detail_level": detail,
            "tone": "data-driven",
            "actionability": "immediate_actions",
            "focus_areas": [],
            "metrics_preference": [],
            "category_specific": {},
            "preference_summary": f"{sentiment} with {category} (rating: {rating}/5)",
            "confidence": 0.3,
            "reasoning": "Fallback based on rating only (LLM unavailable)"
        }

    def merge_preferences(
        self,
        current: Dict,
        new_extract: Dict,
        feedback_count: int,
        rating_delta: float
    ) -> Dict:
        """
        Merge new preferences with existing using weighted update.

        Args:
            current: Current preferences
            new_extract: Newly extracted preferences
            feedback_count: Total feedback count so far
            rating_delta: Change in rating from previous

        Returns:
            Merged preferences dict
        """
        # Calculate update weight
        update_weight = self._calculate_update_weight(
            feedback_count, rating_delta, new_extract.get('confidence', 0.5)
        )

        merged = {}

        # Categorical fields: weighted replacement
        for field in ['detail_level', 'tone', 'actionability']:
            current_val = current.get(field)
            new_val = new_extract.get(field)

            if not current_val:
                # No existing value, use new
                merged[field] = new_val
            elif new_val == current_val:
                # Values match, reinforced
                merged[field] = current_val
            elif update_weight > 0.6:
                # Strong signal to change
                merged[field] = new_val
            else:
                # Weak signal, keep current
                merged[field] = current_val

        # Array fields: merge and deduplicate, limit to 5
        for field in ['focus_areas', 'metrics_preference']:
            current_list = current.get(field, [])
            new_list = new_extract.get(field, [])

            # Combine with new items first (priority)
            combined = new_list + [x for x in current_list if x not in new_list]

            # Limit to top 5
            merged[field] = combined[:5]

        # Summary and metadata
        merged['preference_summary'] = new_extract.get('preference_summary', '')

        # Category-specific preferences (merge dicts)
        merged['category_specific'] = {
            **current.get('category_specific', {}),
            **new_extract.get('category_specific', {})
        }

        # Update confidence score (moving average)
        current_conf = current.get('confidence_score', 0.5)
        new_conf = new_extract.get('confidence', 0.5)
        merged['confidence_score'] = (
            current_conf * (1 - update_weight) + new_conf * update_weight
        )

        return merged

    def _calculate_update_weight(
        self, feedback_count: int, rating_delta: float, confidence: float
    ) -> float:
        """
        Calculate weight for new feedback (0.1-0.9).

        Args:
            feedback_count: Number of previous feedbacks
            rating_delta: Change in rating
            confidence: LLM confidence score

        Returns:
            Weight value between 0.1 and 0.9
        """
        # Base weight decreases logarithmically as feedback accumulates
        # 1st feedback: ~1.0, 10th: ~0.52, 50th: ~0.30
        base_weight = 1.0 / (1.0 + math.log(1 + feedback_count))

        # Amplify based on rating change (normalized 0-1)
        rating_factor = 0.5 + 0.5 * min(rating_delta / 5.0, 1.0)

        # Combine with LLM confidence
        final_weight = base_weight * rating_factor * confidence

        # Clamp to reasonable range
        return max(0.1, min(0.9, final_weight))
