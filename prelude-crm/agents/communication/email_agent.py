"""
Email Summarization Agent - Current Client Focused AI Analysis Engine

A specialized, reusable AI agent that provides intelligent analysis and summarization of email
interactions for a specific current client using OpenAI.
This agent is designed to be used as a common component by other specialized agents that need
client-specific email analysis.

Key Features:
1. Current client focused email analysis from crm_emails table
2. Structured JSON output with Activities/Insights/Next Move format
3. OpenAI-powered AI analysis
4. Activity status based on interaction timestamps (<7 days = active, >7 days = inactive)
5. Three-sentence insights format for proper structure and readability
6. Recent email summary between current employee and current client

Core Analysis Capabilities:
- Current client email content summarization and key point extraction
- Communication pattern analysis for specific client relationships
- Sentiment and tone analysis of client-specific email exchanges
- Action item identification focused on current client needs
- Relationship health assessment for the current client
- Strategic communication insights for current client management

Required Output Format:
All analysis methods return structured JSON output including:
- CLIENT_ID: The current client being analyzed
- ACTIVITIES: List of current client email interactions with status (active/inactive/decline)
- INSIGHTS: Client-specific analysis insights with exactly 3 sentences each
- RECENT_EMAIL_SUMMARY: Most recent email between employee and current client
- NEXT_MOVE: Recommended actions based on current client email analysis

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)
"""

import os
import json
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from agents.core.model_factory import ModelFactory
from service_core.llm_json import extract_json

# Load environment variables from .env file
load_dotenv()


class EmailAgent:
    """
    Current Client Focused AI-powered Email Analysis Agent

    This agent provides email analysis capabilities focused on a specific current client
    that can be used by other specialized agents. It accepts email interaction data for
    a specific client and provides structured analysis based on the Activities/Insights/
    Next Move format with recent email summary functionality.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None):
        """
        Initialize the Email Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Email Agent",
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
            system_message = "You are an expert email communication analyst with expertise in analyzing email patterns, extracting key insights, and providing actionable recommendations. You must follow the specified JSON output format exactly, including Activities/Insights/Next Move structure with proper formatting."

        return self.model_factory.generate_content(prompt, system_message)

    def _determine_activity_status(self, interaction_date: str) -> str:
        """
        Determine activity status based on interaction timestamp
        
        Args:
            interaction_date: ISO format date string
            
        Returns:
            Status: 'active' if <7 days, 'inactive' if >7 days, 'churned' if no interactions
        """
        try:
            if not interaction_date:
                return "churned"
            
            # Parse the date
            if isinstance(interaction_date, str):
                interaction_dt = datetime.fromisoformat(interaction_date.replace('Z', '+00:00'))
            else:
                interaction_dt = interaction_date
            if interaction_dt.tzinfo is None:
                interaction_dt = interaction_dt.replace(tzinfo=timezone.utc)

            # Calculate days since interaction
            days_since = (datetime.now(timezone.utc) - interaction_dt).days
            
            if days_since < 7:
                return "active"
            else:
                return "inactive"
                
        except Exception:
            return "churned"

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
                # It's a datetime object
                return date_value.strftime('%Y-%m-%d')
            elif isinstance(date_value, str):
                # It's already a string, take first 10 chars for YYYY-MM-DD format
                return date_value[:10]
            else:
                # Convert to string and take first 10 chars
                return str(date_value)[:10]
        except Exception:
            return "N/A"

    def format_email_interactions_for_analysis(self,
                                             interactions_data: List[Dict[str, Any]],
                                             context: str = "email_analysis") -> str:
        """
        Format email data for LLM analysis.

        Note: Email data should come from crm_emails table, NOT interaction_details.
        The interaction_details table only contains calls and meetings.

        Args:
            interactions_data: List of email records from crm_emails
            context: Analysis context

        Returns:
            Formatted string ready for LLM processing
        """
        if not interactions_data:
            return "No email data available for analysis."

        # Use all provided data directly (no type filtering needed —
        # caller is responsible for passing email data from crm_emails)
        email_interactions = interactions_data

        if not email_interactions:
            return "No email data found in the provided data."

        # Build formatted output
        formatted_data = f"=== EMAIL ANALYSIS CONTEXT: {context.upper()} ===\n"

        # Calculate summary statistics
        total_emails = len(email_interactions)
        recent_emails = len([e for e in email_interactions if self._determine_activity_status(e.get('created_at')) == 'active'])

        # Get client information if available
        client_id = email_interactions[0].get('customer_id') if email_interactions else 'N/A'

        formatted_data += f"""
=== CURRENT CLIENT EMAIL INTERACTION SUMMARY ===
Client ID: {client_id}
Total Email Interactions: {total_emails}
Recent Email Activity (last 7 days): {recent_emails}
Analysis Period: {email_interactions[0].get('created_at', 'N/A')} to {email_interactions[-1].get('created_at', 'N/A')}
Focus: Single client email communication analysis
"""

        formatted_data += "\n=== EMAIL INTERACTION DETAILS ===\n"
        
        # Sort emails by date (most recent first)
        sorted_emails = sorted(email_interactions, key=lambda x: x.get('created_at', ''), reverse=True)
        
        for i, email in enumerate(sorted_emails, 1):
            status = self._determine_activity_status(email.get('created_at'))
            status_emoji = "🟢" if status == "active" else "🟡" if status == "inactive" else "🔴"
            
            formatted_data += f"""
Email #{i}: {email.get('type', 'Email')} {status_emoji}
  Date: {email.get('created_at', 'N/A')}
  Subject: {email.get('subject', 'N/A')}
  From: {email.get('from_email', 'N/A')}
  To: {email.get('to_email', 'N/A')}
  Direction: {email.get('direction', 'N/A')}
  Content: {(email.get('body') or email.get('content') or 'No content available')[:200]}{'...' if len(email.get('body') or email.get('content') or '') > 200 else ''}
  Status: {status}
"""

        return formatted_data

    def _get_most_recent_email_summary(self,
                                     interactions_data: List[Dict[str, Any]],
                                     employee_id: int = None,
                                     client_id: int = None) -> Dict[str, Any]:
        """
        Get summary of the most recent email interaction between specific employee and client

        Args:
            interactions_data: List of interaction records
            employee_id: Specific employee ID to filter by
            client_id: Specific client ID to filter by

        Returns:
            Dictionary with most recent email summary information
        """
        # Use all provided data (caller passes email data from crm_emails)
        email_interactions = list(interactions_data)

        # Further filter by employee and client if specified
        if employee_id is not None:
            email_interactions = [e for e in email_interactions if e.get('employee_id') == employee_id]
        if client_id is not None:
            email_interactions = [e for e in email_interactions if e.get('customer_id') == client_id]

        if not email_interactions:
            return {
                "has_recent_email": False,
                "message": "No email interactions found for the specified criteria"
            }

        # Sort by date to get the most recent
        sorted_emails = sorted(email_interactions, key=lambda x: x.get('created_at', ''), reverse=True)
        most_recent = sorted_emails[0]

        # Generate summary of the most recent email
        content = most_recent.get('body') or most_recent.get('content') or ''
        content_preview = content[:150] + "..." if len(content) > 150 else content

        return {
            "has_recent_email": True,
            "email_date": self._format_date_safely(most_recent.get('created_at', '')),
            "employee_id": most_recent.get('employee_id'),
            "client_id": most_recent.get('customer_id'),
            "email_type": most_recent.get('type', 'Email'),
            "content_preview": content_preview,
            "full_content": content,
            "duration_minutes": most_recent.get('duration_minutes', 0),
            "status": self._determine_activity_status(most_recent.get('created_at')),
            "gmail_message_id": most_recent.get('gmail_message_id', '')
        }

    def analyze_email_communications(self,
                                   interactions_data: List[Dict[str, Any]],
                                   client_id: int,
                                   analysis_focus: str = "comprehensive",
                                   employee_id: int = None) -> Dict[str, Any]:
        """
        Analyze email communications for a specific current client with structured JSON output format

        Args:
            interactions_data: List of interaction records
            client_id: Current client ID to focus analysis on (REQUIRED)
            analysis_focus: Focus area ("comprehensive", "sentiment", "patterns", "actions")
            employee_id: Optional specific employee ID to filter by

        Returns:
            Structured JSON with Activities/Insights/Next Move format focused on the current client
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 EmailAgent [Customer {client_id}]: Starting email communications analysis")
        logger.info(f"📊 EmailAgent [Customer {client_id}]: Received {len(interactions_data)} total interactions")
        logger.info(f"🎯 EmailAgent [Customer {client_id}]: Analysis focus: {analysis_focus}, Employee filter: {employee_id}")

        # Filter interactions for the current client only
        client_interactions = [
            interaction for interaction in interactions_data
            if interaction.get('customer_id') == client_id
        ]

        if not client_interactions:
            logger.warning(f"⚠️ EmailAgent [Customer {client_id}]: No interactions found for this client")
            return {
                "error": f"No interactions found for client_id {client_id}",
                "client_id": client_id
            }

        formatted_data = self.format_email_interactions_for_analysis(client_interactions, context=f"email_communication_analysis_for_client_{client_id}")

        # Use all provided data (caller passes email data from crm_emails)
        email_interactions = client_interactions

        # Get most recent email summary for current client
        recent_email_summary = self._get_most_recent_email_summary(client_interactions, employee_id, client_id)

        focus_prompts = {
            "comprehensive": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Communication Patterns",
      "insight": "Three sentence insight about communication patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Content Analysis",
      "insight": "Three sentence insight about email content themes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Relationship Health",
      "insight": "Three sentence insight about relationship status. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_email_summary": {
    "has_recent_email": true/false,
    "email_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "email_type": "Email/Follow-up Email",
    "content_preview": "First 150 characters of email content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent email"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Specific recommended action",
    "rationale": "Why this action is recommended"
  }
}""",

            "sentiment": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Sentiment Analysis",
      "insight": "Three sentence insight about overall sentiment trends. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Tone Evolution",
      "insight": "Three sentence insight about how tone has changed over time. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Emotional Indicators",
      "insight": "Three sentence insight about emotional cues in communications. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_email_summary": {
    "has_recent_email": true/false,
    "email_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "email_type": "Email/Follow-up Email",
    "content_preview": "First 150 characters of email content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent email"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Sentiment-based recommended action",
    "rationale": "Why this action addresses sentiment concerns"
  }
}""",

            "patterns": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Communication Frequency",
      "insight": "Three sentence insight about email frequency patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Response Patterns",
      "insight": "Three sentence insight about response time and engagement patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Topic Trends",
      "insight": "Three sentence insight about recurring topics and themes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_email_summary": {
    "has_recent_email": true/false,
    "email_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "email_type": "Email/Follow-up Email",
    "content_preview": "First 150 characters of email content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent email"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Pattern-based recommended action",
    "rationale": "Why this action leverages identified patterns"
  }
}""",

            "actions": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Action Items Identified",
      "insight": "Three sentence insight about action items mentioned in emails. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Follow-up Requirements",
      "insight": "Three sentence insight about follow-up needs and commitments. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Priority Assessment",
      "insight": "Three sentence insight about priority levels of different actions. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_email_summary": {
    "has_recent_email": true/false,
    "email_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "email_type": "Email/Follow-up Email",
    "content_preview": "First 150 characters of email content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent email"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Action-focused recommended next step",
    "rationale": "Why this action addresses the most critical needs"
  }
}"""
        }

        system_message = f"""You are an expert email communication analyst. You MUST return valid JSON in the exact format specified.

CRITICAL REQUIREMENTS:
1. Each insight must contain exactly 3 sentences
2. Activity status must be 'active' if interaction is <7 days old, 'inactive' if >7 days old, 'decline' if no recent interactions
3. Return only valid JSON - no additional text or formatting
4. Use the actual email data provided to populate activities and insights

Focus on {analysis_focus} analysis of the email communications."""

        prompt = f"""Analyze the following email communication data and return structured JSON:

{formatted_data}

{focus_prompts.get(analysis_focus, focus_prompts['comprehensive'])}

IMPORTANT:
- Return ONLY valid JSON in the specified format
- Each insight must be exactly 3 sentences
- Use actual dates and content from the email data
- Determine activity status based on interaction timestamps"""

        response = self._generate_content(prompt, system_message)

        try:
            result = extract_json(response)
            if not isinstance(result, dict):
                raise json.JSONDecodeError("No JSON object found", response, 0)

            # Add recent email summary to the result
            if recent_email_summary['has_recent_email']:
                # Handle datetime formatting properly
                email_date = recent_email_summary['email_date']
                if email_date:
                    if hasattr(email_date, 'strftime'):
                        # It's a datetime object
                        formatted_date = email_date.strftime('%Y-%m-%d')
                    elif isinstance(email_date, str):
                        # It's already a string, take first 10 chars
                        formatted_date = email_date[:10]
                    else:
                        formatted_date = str(email_date)[:10]
                else:
                    formatted_date = "N/A"

                result['recent_email_summary'] = {
                    "has_recent_email": True,
                    "email_date": formatted_date,
                    "employee_id": recent_email_summary['employee_id'],
                    "client_id": recent_email_summary['client_id'],
                    "email_type": recent_email_summary['email_type'],
                    "content_preview": recent_email_summary['content_preview'],
                    "status": recent_email_summary['status'],
                    "key_points": f"Most recent email from {formatted_date}: {recent_email_summary['content_preview']}"
                }
            else:
                result['recent_email_summary'] = {
                    "has_recent_email": False,
                    "message": recent_email_summary.get('message', 'No recent email found')
                }

            return result

        except json.JSONDecodeError:
            # Fallback structured response if JSON parsing fails
            fallback_result = {
                "activities": [
                    {
                        "type": "email",
                        "date": self._format_date_safely(email.get('created_at', '')) if email_interactions else "N/A",
                        "content_summary": "Email communication analysis",
                        "status": self._determine_activity_status(email_interactions[0].get('created_at') if email_interactions else None)
                    }
                ],
                "insights": [
                    {
                        "category": "Analysis Status",
                        "insight": "Email analysis was requested but encountered processing challenges. The system attempted to analyze the provided email communications. Manual review of the email content may be needed for detailed insights."
                    }
                ],
                "next_move": {
                    "priority": "medium",
                    "action": "Review email communications manually",
                    "rationale": "Automated analysis encountered issues, manual review recommended"
                }
            }

            # Add recent email summary to fallback result
            if recent_email_summary['has_recent_email']:
                formatted_date = self._format_date_safely(recent_email_summary['email_date'])
                fallback_result['recent_email_summary'] = {
                    "has_recent_email": True,
                    "email_date": formatted_date,
                    "employee_id": recent_email_summary['employee_id'],
                    "client_id": recent_email_summary['client_id'],
                    "email_type": recent_email_summary['email_type'],
                    "content_preview": recent_email_summary['content_preview'],
                    "status": recent_email_summary['status'],
                    "key_points": f"Most recent email from {formatted_date}: {recent_email_summary['content_preview']}"
                }
            else:
                fallback_result['recent_email_summary'] = {
                    "has_recent_email": False,
                    "message": recent_email_summary.get('message', 'No recent email found')
                }

            return fallback_result

    def generate_email_insights(self,
                              interactions_data: List[Dict[str, Any]],
                              client_id: int,
                              insight_type: str = "strategic",
                              employee_id: int = None) -> Dict[str, Any]:
        """
        Generate specific insights from email data for a specific current client with structured JSON output format

        Args:
            interactions_data: List of interaction records
            client_id: Current client ID to focus analysis on (REQUIRED)
            insight_type: Type of insights ("strategic", "tactical", "relationship", "content")
            employee_id: Optional specific employee ID to filter by

        Returns:
            Structured JSON with Activities/Insights/Next Move format focused on the current client
        """
        # Filter interactions for the current client only
        client_interactions = [
            interaction for interaction in interactions_data
            if interaction.get('customer_id') == client_id
        ]

        if not client_interactions:
            return {
                "error": f"No interactions found for client_id {client_id}",
                "client_id": client_id
            }

        formatted_data = self.format_email_interactions_for_analysis(client_interactions, context=f"email_insights_generation_for_client_{client_id}")

        # Use all provided data (caller passes email data from crm_emails)
        email_interactions = client_interactions

        # Get most recent email summary for current client
        recent_email_summary = self._get_most_recent_email_summary(client_interactions, employee_id, client_id)

        insight_prompts = {
            "strategic": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Strategic Communication Opportunities",
      "insight": "Three sentence insight about strategic opportunities identified in email communications. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Relationship Development",
      "insight": "Three sentence insight about relationship building through email interactions. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Business Impact Assessment",
      "insight": "Three sentence insight about business impact of email communications. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_email_summary": {
    "has_recent_email": true/false,
    "email_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "email_type": "Email/Follow-up Email",
    "content_preview": "First 150 characters of email content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent email"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Strategic action based on email analysis",
    "rationale": "Strategic reasoning for recommended action"
  }
}""",

            "tactical": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Immediate Action Items",
      "insight": "Three sentence insight about immediate actions needed based on emails. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Process Improvements",
      "insight": "Three sentence insight about process improvements identified from email patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Response Optimization",
      "insight": "Three sentence insight about optimizing email response strategies. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "next_move": {
    "priority": "high/medium/low",
    "action": "Tactical action for immediate implementation",
    "rationale": "Tactical reasoning for recommended action"
  }
}""",

            "relationship": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Relationship Health",
      "insight": "Three sentence insight about current relationship health based on email tone and frequency. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Engagement Levels",
      "insight": "Three sentence insight about engagement levels and responsiveness patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Trust Indicators",
      "insight": "Three sentence insight about trust and rapport indicators in email communications. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "next_move": {
    "priority": "high/medium/low",
    "action": "Relationship-focused action",
    "rationale": "Relationship-based reasoning for recommended action"
  }
}""",

            "content": """REQUIRED JSON OUTPUT FORMAT:
{
  "activities": [
    {
      "type": "email",
      "date": "YYYY-MM-DD",
      "content_summary": "Brief summary of email content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Content Themes",
      "insight": "Three sentence insight about recurring themes and topics in email content. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Information Quality",
      "insight": "Three sentence insight about quality and completeness of information shared. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Communication Clarity",
      "insight": "Three sentence insight about clarity and effectiveness of email communications. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "next_move": {
    "priority": "high/medium/low",
    "action": "Content-focused improvement action",
    "rationale": "Content-based reasoning for recommended action"
  }
}"""
        }

        system_message = f"""You are an expert email communication analyst. You MUST return valid JSON in the exact format specified.

CRITICAL REQUIREMENTS:
1. Each insight must contain exactly 3 sentences
2. Activity status must be 'active' if interaction is <7 days old, 'inactive' if >7 days old, 'decline' if no recent interactions
3. Return only valid JSON - no additional text or formatting
4. Use the actual email data provided to populate activities and insights

Focus on {insight_type} insights from the email communications."""

        prompt = f"""Generate {insight_type} insights from the following email communication data and return structured JSON:

{formatted_data}

{insight_prompts.get(insight_type, insight_prompts['strategic'])}

IMPORTANT:
- Return ONLY valid JSON in the specified format
- Each insight must be exactly 3 sentences
- Use actual dates and content from the email data
- Determine activity status based on interaction timestamps"""

        response = self._generate_content(prompt, system_message)

        try:
            result = extract_json(response)
            if not isinstance(result, dict):
                raise json.JSONDecodeError("No JSON object found", response, 0)

            # Add recent email summary to the result
            if recent_email_summary['has_recent_email']:
                formatted_date = self._format_date_safely(recent_email_summary['email_date'])
                result['recent_email_summary'] = {
                    "has_recent_email": True,
                    "email_date": formatted_date,
                    "employee_id": recent_email_summary['employee_id'],
                    "client_id": recent_email_summary['client_id'],
                    "email_type": recent_email_summary['email_type'],
                    "content_preview": recent_email_summary['content_preview'],
                    "status": recent_email_summary['status'],
                    "key_points": f"Most recent email from {formatted_date}: {recent_email_summary['content_preview']}"
                }
            else:
                result['recent_email_summary'] = {
                    "has_recent_email": False,
                    "message": recent_email_summary.get('message', 'No recent email found')
                }

            return result

        except json.JSONDecodeError:
            # Fallback structured response if JSON parsing fails
            fallback_result = {
                "activities": [
                    {
                        "type": "email",
                        "date": self._format_date_safely(email.get('created_at', '')) if email_interactions else "N/A",
                        "content_summary": f"Email {insight_type} analysis",
                        "status": self._determine_activity_status(email_interactions[0].get('created_at') if email_interactions else None)
                    }
                ],
                "insights": [
                    {
                        "category": f"{insight_type.title()} Analysis",
                        "insight": f"Email {insight_type} analysis was requested but encountered processing challenges. The system attempted to analyze the provided email communications for {insight_type} insights. Manual review of the email content may be needed for detailed {insight_type} assessment."
                    }
                ],
                "next_move": {
                    "priority": "medium",
                    "action": f"Review email communications for {insight_type} insights",
                    "rationale": f"Automated {insight_type} analysis encountered issues, manual review recommended"
                }
            }

            # Add recent email summary to fallback result
            if recent_email_summary['has_recent_email']:
                formatted_date = self._format_date_safely(recent_email_summary['email_date'])
                fallback_result['recent_email_summary'] = {
                    "has_recent_email": True,
                    "email_date": formatted_date,
                    "employee_id": recent_email_summary['employee_id'],
                    "client_id": recent_email_summary['client_id'],
                    "email_type": recent_email_summary['email_type'],
                    "content_preview": recent_email_summary['content_preview'],
                    "status": recent_email_summary['status'],
                    "key_points": f"Most recent email from {formatted_date}: {recent_email_summary['content_preview']}"
                }
            else:
                fallback_result['recent_email_summary'] = {
                    "has_recent_email": False,
                    "message": recent_email_summary.get('message', 'No recent email found')
                }

            return fallback_result
