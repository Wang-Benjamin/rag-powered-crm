"""
User Preference Agent
=====================
Analyzes user preferences and company profile using GPT models.
Generates intelligent summaries from company profile, HS codes, factory details,
guardrails, and additional context for the pivot to Asia-to-West bridge.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

GUARDRAIL_KEY_LABELS = {
    # Topics to Avoid
    "competitorComparisons": "Competitor comparisons",
    "pricingNegotiations": "Pricing & discount negotiations",
    "regulatoryAdvice": "Regulatory/customs advice",
    "sanctionsParties": "Sanctions & restricted parties",
    "paymentTerms": "Payment terms commitments",
    "legalClaims": "Contractual & legal claims",
    "politicalOpinions": "Political & trade policy opinions",
    "shipmentDelays": "Shipment delay explanations",
    # Hard Restrictions
    "noShipmentDates": "Never confirm shipment dates in writing",
    "noPriceQuotes": "Never quote prices without approval",
    "noDutyRates": "Never discuss specific duty/tariff rates",
    "alwaysDisclaimer": "Always include regulatory disclaimer",
    "noCompetitorNames": "Never mention competitors by name",
    "noCreditTerms": "Never commit to credit terms",
    # Prohibited Statements
    "noCustomsBroker": "Don't claim to be a customs broker",
    "noDeliveryGuarantee": "Don't guarantee delivery timelines",
    "noRegulatoryFilings": "Don't reference regulatory filings",
    "noLitigationDiscussion": "Don't discuss pending litigation",
}


class UserPreferenceAgent:
    """Agent for analyzing user preferences using GPT models."""

    def __init__(self):
        """Initialize the agent with OpenAI client."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4.1-mini")
        self.provider = os.getenv("DEFAULT_PROVIDER", "openai")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"UserPreferenceAgent initialized with model: {self.model}")

    def analyze_preferences(
        self,
        company_profile: Dict[str, Any],
        hs_codes: list,
        factory_details: Dict[str, Any],
        guardrails: Dict[str, Any],
        additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze user preferences and generate an intelligent summary using GPT.

        Args:
            company_profile: Company identity (name, location, product description, etc.)
            hs_codes: Confirmed HS codes [{code, description, confidence, confirmed}]
            factory_details: Factory info (capacity, lead time, MOQ, etc.)
            guardrails: Guardrail preferences (topics to avoid, claims restrictions)
            additional_context: Additional context provided by user

        Returns:
            dict: Structured AI-generated summary with keys:
                - communication_style: How the AI should communicate for this manufacturer
                - boundaries_restrictions: What the AI should avoid
                - product_market_focus: Product and market positioning insights
                - key_recommendations: Key recommendations
                - full_summary: Complete summary text
        """
        try:
            prompt = self._build_analysis_prompt(company_profile, hs_codes, factory_details, guardrails, additional_context)

            logger.info("Sending preferences to GPT for analysis")
            logger.debug(f"Prompt length: {len(prompt)} characters")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant specialized in analyzing manufacturer profiles for cross-border B2B trade. "
                            "Your task is to synthesize company profile, product data, factory details, and communication preferences "
                            "into a structured JSON format that guides AI-powered buyer communication. "
                            "The manufacturer is selling to Western (primarily US) buyers. Communication should always be "
                            "professional Western B2B standard — polished, quantified, and culturally appropriate. "
                            "Return a JSON object with these exact keys: "
                            "'communication_style', 'boundaries_restrictions', 'product_market_focus', 'key_recommendations'. "
                            "Each value should be a clear, concise paragraph (2-4 sentences). "
                            "DO NOT include any markdown formatting, just return valid JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            summary_text = response.choices[0].message.content.strip()

            try:
                summary_json = json.loads(summary_text)
                summary_json["full_summary"] = self._format_full_summary(summary_json)

                logger.info("Successfully generated structured preference summary")
                return summary_json
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GPT response as JSON: {e}")
                return self._generate_fallback_summary(company_profile, hs_codes, factory_details, guardrails, additional_context)

        except Exception as e:
            logger.error(f"Error analyzing preferences with GPT: {e}")
            return self._generate_fallback_summary(company_profile, hs_codes, factory_details, guardrails, additional_context)

    def _build_analysis_prompt(
        self,
        company_profile: Dict[str, Any],
        hs_codes: list,
        factory_details: Dict[str, Any],
        guardrails: Dict[str, Any],
        additional_context: Dict[str, Any]
    ) -> str:
        """Build a detailed prompt for GPT analysis."""
        prompt_parts = [
            "Please analyze the following manufacturer profile and create a comprehensive summary for guiding AI-powered buyer communication:\n"
        ]

        # Company profile section
        if company_profile:
            prompt_parts.append("\n## Company Profile")
            if company_profile.get('company_name_en'):
                prompt_parts.append(f"- Company: {company_profile['company_name_en']}")
            if company_profile.get('company_name_zh'):
                prompt_parts.append(f"- Chinese name: {company_profile['company_name_zh']}")
            if company_profile.get('location'):
                prompt_parts.append(f"- Location: {company_profile['location']}")
            if company_profile.get('product_description_en') or company_profile.get('product_description'):
                desc = company_profile.get('product_description_en', company_profile.get('product_description', ''))
                prompt_parts.append(f"- Products: {desc}")

        # HS codes section
        confirmed_codes = [c for c in (hs_codes or []) if c.get('confirmed')]
        if confirmed_codes:
            prompt_parts.append("\n## Product Classification (HS Codes)")
            for code in confirmed_codes:
                prompt_parts.append(f"- {code.get('code', '')} — {code.get('description', '')}")

        # Factory details section
        if factory_details:
            prompt_parts.append("\n## Factory Capabilities")
            if factory_details.get('capacity'):
                prompt_parts.append(f"- Production capacity: {factory_details['capacity']}")
            if factory_details.get('lead_time'):
                prompt_parts.append(f"- Lead time: {factory_details['lead_time']}")
            if factory_details.get('moq'):
                prompt_parts.append(f"- Minimum order quantity: {factory_details['moq']}")
            if factory_details.get('year_established'):
                prompt_parts.append(f"- Established: {factory_details['year_established']}")
            if factory_details.get('employees'):
                prompt_parts.append(f"- Employees: {factory_details['employees']}")

        # Guardrails section
        if guardrails and any(guardrails.values()):
            normalized = self._normalize_guardrails(guardrails)
            prompt_parts.append("\n## Communication Guardrails & Restrictions")
            if normalized.get('topicsToAvoid'):
                prompt_parts.append(f"- Topics requiring caution: {normalized['topicsToAvoid']}")
            if normalized.get('hardRestrictions'):
                prompt_parts.append(f"- Hard restrictions: {normalized['hardRestrictions']}")
            if normalized.get('prohibitedStatements'):
                prompt_parts.append(f"- Prohibited statements: {normalized['prohibitedStatements']}")

        # Additional context section
        if additional_context and additional_context.get('additionalContext'):
            prompt_parts.append("\n## Additional Context")
            prompt_parts.append(f"{additional_context['additionalContext']}")

        prompt_parts.append(
            "\n\nPlease synthesize this manufacturer profile into a clear, actionable summary that can guide "
            "AI-powered communication with Western buyers. The tone should always be professional Western B2B standard. "
            "Structure your response with sections for: "
            "1) Communication Style (how to present this manufacturer to Western buyers), "
            "2) Boundaries & Restrictions, "
            "3) Product & Market Focus (key selling points, competitive positioning), "
            "and 4) Key Recommendations."
        )

        return "\n".join(prompt_parts)

    def _normalize_guardrails(self, guardrails: dict) -> dict:
        """Normalize legacy key names and resolve predefined keys to human-readable labels."""
        key_map = {"guardrailTopics": "topicsToAvoid", "avoidTopics": "hardRestrictions", "otherClaims": "prohibitedStatements"}
        result = {}
        for old_key, new_key in key_map.items():
            val = guardrails.get(new_key) or guardrails.get(old_key)
            if isinstance(val, list):
                val = ", ".join(
                    GUARDRAIL_KEY_LABELS.get(v, v.removeprefix("custom:")) for v in val
                )
            elif isinstance(val, str):
                val = val  # legacy string, use as-is
            else:
                val = ""
            result[new_key] = val
        return result

    def _format_full_summary(self, summary_json: Dict[str, Any]) -> str:
        """Format structured JSON summary into readable text."""
        sections = []

        if summary_json.get('communication_style'):
            sections.append(f"Communication Style:\n{summary_json['communication_style']}")

        if summary_json.get('boundaries_restrictions'):
            sections.append(f"Boundaries & Restrictions:\n{summary_json['boundaries_restrictions']}")

        if summary_json.get('product_market_focus'):
            sections.append(f"Product & Market Focus:\n{summary_json['product_market_focus']}")

        if summary_json.get('key_recommendations'):
            sections.append(f"Key Recommendations:\n{summary_json['key_recommendations']}")

        return "\n\n".join(sections)

    def _generate_fallback_summary(
        self,
        company_profile: Dict[str, Any],
        hs_codes: list,
        factory_details: Dict[str, Any],
        guardrails: Dict[str, Any],
        additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a basic fallback summary if GPT analysis fails."""
        communication_style = "Use professional Western B2B communication standards. Be quantified, direct, and culturally appropriate for US/EU buyers."

        # Build boundaries
        boundaries_parts = []
        if guardrails and any(guardrails.values()):
            normalized = self._normalize_guardrails(guardrails)
            if normalized.get('topicsToAvoid'):
                boundaries_parts.append(f"Avoid topics: {normalized['topicsToAvoid']}.")
            if normalized.get('hardRestrictions'):
                boundaries_parts.append(f"Hard restrictions: {normalized['hardRestrictions']}.")
            if normalized.get('prohibitedStatements'):
                boundaries_parts.append(f"Prohibited statements: {normalized['prohibitedStatements']}.")

        # Build product focus
        product_parts = []
        if company_profile:
            desc = company_profile.get('product_description_en', company_profile.get('product_description', ''))
            if desc:
                product_parts.append(f"Products: {desc}.")
        confirmed_codes = [c for c in (hs_codes or []) if c.get('confirmed')]
        if confirmed_codes:
            codes_str = ", ".join(f"{c['code']} ({c.get('description', '')})" for c in confirmed_codes)
            product_parts.append(f"HS codes: {codes_str}.")
        if factory_details:
            if factory_details.get('capacity'):
                product_parts.append(f"Capacity: {factory_details['capacity']}.")
            if factory_details.get('lead_time'):
                product_parts.append(f"Lead time: {factory_details['lead_time']}.")

        # Build key recommendations
        key_recommendations = []
        if additional_context and additional_context.get('additionalContext'):
            key_recommendations.append(additional_context['additionalContext'])

        result = {
            "communication_style": communication_style,
            "boundaries_restrictions": " ".join(boundaries_parts) if boundaries_parts else "No specific restrictions provided.",
            "product_market_focus": " ".join(product_parts) if product_parts else "No specific product focus provided.",
            "key_recommendations": " ".join(key_recommendations) if key_recommendations else "No additional recommendations provided."
        }

        result["full_summary"] = self._format_full_summary(result)
        return result


# Singleton instance
_agent_instance: Optional[UserPreferenceAgent] = None


def get_user_preference_agent() -> UserPreferenceAgent:
    """Get or create singleton instance of UserPreferenceAgent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = UserPreferenceAgent()
    return _agent_instance
