"""
Note Summarization Agent - Current Client Focused AI Analysis Engine

A specialized, reusable AI agent that provides intelligent analysis and summarization of
employee-client notes for a specific current client using multiple LLM providers (Google Gemini and OpenAI). 
This agent is designed to be used as a common component by other specialized agents that need 
client-specific note analysis.

Key Features:
1. Current client focused note analysis from employee_client_notes field
2. Structured JSON output with Activities/Insights/Next Move format
3. Multi-provider AI support (Gemini, OpenAI)
4. Activity status based on note timestamps (<7 days = active, >7 days = inactive)
5. Three-sentence insights format for proper structure and readability
6. Recent note summary between current employee and current client

Core Analysis Capabilities:
- Current client note content summarization and key point extraction
- Communication pattern analysis for specific client relationships through notes
- Sentiment and tone analysis of client-specific note entries
- Action item identification focused on current client needs from notes
- Relationship health assessment for the current client based on notes
- Strategic insights for current client management from note history

Required Output Format:
All analysis methods return structured JSON output including:
- CLIENT_ID: The current client being analyzed
- ACTIVITIES: List of current client note interactions with status (active/inactive/decline)
- INSIGHTS: Client-specific analysis insights with exactly 3 sentences each
- RECENT_NOTE_SUMMARY: Most recent note between employee and current client
- NEXT_MOVE: Recommended actions based on current client note analysis

Supported Providers:
- Google Gemini (gemini-1.5-flash, gemini-1.5-pro)
- OpenAI (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
"""

import os
import json
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from agents.core.model_factory import ModelFactory

# Load environment variables from .env file
load_dotenv()


class NoteAgent:
    """
    Current Client Focused AI-powered Note Analysis Agent
    
    This agent provides note analysis capabilities focused on a specific current client
    that can be used by other specialized agents. It accepts employee-client note data for
    a specific client and provides structured analysis based on the Activities/Insights/
    Next Move format with recent note summary functionality.
    """

    def __init__(self,
                 provider: str = "openai",
                 model_name: str = None,
                 openai_api_key: str = None):
        """
        Initialize the Note Agent with OpenAI support

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
        """
        # Initialize model factory
        self.model_factory = ModelFactory.create_for_agent(
            agent_name="Note Agent",
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
            system_message = "You are an expert client relationship analyst with expertise in analyzing employee-client notes, extracting key insights, and providing actionable recommendations. You must follow the specified JSON output format exactly, including Activities/Insights/Next Move structure with proper formatting."

        return self.model_factory.generate_content(prompt, system_message)

    def _determine_activity_status(self, note_date: str) -> str:
        """
        Determine activity status based on note timestamp
        
        Args:
            note_date: ISO format date string
            
        Returns:
            Status: 'active' if <7 days, 'inactive' if >7 days, 'churned' if no notes
        """
        try:
            if not note_date:
                return "churned"
            
            # Parse the date
            if isinstance(note_date, str):
                note_dt = datetime.fromisoformat(note_date.replace('Z', '+00:00'))
            else:
                note_dt = note_date
            if note_dt.tzinfo is None:
                note_dt = note_dt.replace(tzinfo=timezone.utc)

            # Calculate days since note
            days_since = (datetime.now(timezone.utc) - note_dt).days
            
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

    def _get_most_recent_note_summary(self,
                                    notes_data: List[Dict[str, Any]], 
                                    employee_id: int = None, 
                                    client_id: int = None) -> Dict[str, Any]:
        """
        Get summary of the most recent note between specific employee and client
        
        Args:
            notes_data: List of note records
            employee_id: Specific employee ID to filter by
            client_id: Specific client ID to filter by
            
        Returns:
            Dictionary with most recent note summary information
        """
        # Filter notes
        filtered_notes = notes_data
        
        # Further filter by employee and client if specified
        if employee_id is not None:
            filtered_notes = [n for n in filtered_notes if n.get('employee_id') == employee_id]
        if client_id is not None:
            filtered_notes = [n for n in filtered_notes if n.get('client_id') == client_id]
        
        if not filtered_notes:
            return {
                "has_recent_note": False,
                "message": "No notes found for the specified criteria"
            }
        
        # Sort by date to get the most recent
        sorted_notes = sorted(filtered_notes, key=lambda x: x.get('created_at', ''), reverse=True)
        most_recent = sorted_notes[0]
        
        # Generate summary of the most recent note
        title = most_recent.get('title', '')
        body = most_recent.get('body', '')
        content_preview = f"{title}: {body}"[:150] + "..." if len(f"{title}: {body}") > 150 else f"{title}: {body}"
        
        return {
            "has_recent_note": True,
            "note_date": self._format_date_safely(most_recent.get('created_at', '')),
            "employee_id": most_recent.get('employee_id'),
            "client_id": most_recent.get('client_id'),
            "note_title": title,
            "content_preview": content_preview,
            "full_body": body,
            "status": self._determine_activity_status(most_recent.get('created_at')),
            "note_id": most_recent.get('note_id', '')
        }

    def format_notes_for_analysis(self,
                                 notes_data: List[Dict[str, Any]],
                                 context: str = "note_analysis") -> str:
        """
        Format note data for LLM analysis

        Args:
            notes_data: List of note records
            context: Analysis context

        Returns:
            Formatted string ready for LLM processing
        """
        if not notes_data:
            return "No note data available for analysis."

        # Build formatted output
        formatted_data = f"=== NOTE ANALYSIS CONTEXT: {context.upper()} ===\n"

        # Calculate summary statistics
        total_notes = len(notes_data)
        recent_notes = len([n for n in notes_data if self._determine_activity_status(n.get('created_at')) == 'active'])

        # Get client information if available
        client_id = notes_data[0].get('client_id') if notes_data else 'N/A'

        formatted_data += f"""
=== CURRENT CLIENT NOTE SUMMARY ===
Client ID: {client_id}
Total Notes: {total_notes}
Recent Notes (last 7 days): {recent_notes}
Analysis Period: {notes_data[0].get('created_at', 'N/A')} to {notes_data[-1].get('created_at', 'N/A')}
Focus: Single client note analysis
"""

        formatted_data += "\n=== INDIVIDUAL NOTE DETAILS ===\n"

        # Sort notes by date (most recent first)
        sorted_notes = sorted(notes_data, key=lambda x: x.get('created_at', ''), reverse=True)

        for i, note in enumerate(sorted_notes, 1):
            status = self._determine_activity_status(note.get('created_at'))
            status_emoji = "🟢" if status == "active" else "🟡" if status == "inactive" else "🔴"

            formatted_data += f"""
Note #{i}: {note.get('title', 'Untitled Note')} {status_emoji}
  Date: {note.get('created_at', 'N/A')}
  Employee ID: {note.get('employee_id', 'N/A')}
  Client ID: {note.get('client_id', 'N/A')}
  Content: {note.get('body', 'No content available')[:200]}{'...' if len(note.get('body', '')) > 200 else ''}
  Status: {status}
"""

        return formatted_data

    def analyze_client_notes(self,
                           notes_data: List[Dict[str, Any]],
                           client_id: int,
                           analysis_focus: str = "comprehensive",
                           employee_id: int = None) -> Dict[str, Any]:
        """
        Analyze client notes for a specific current client with structured JSON output format

        Args:
            notes_data: List of note records
            client_id: Current client ID to focus analysis on (REQUIRED)
            analysis_focus: Focus area ("comprehensive", "sentiment", "patterns", "actions")
            employee_id: Optional specific employee ID to filter by

        Returns:
            Structured JSON with Activities/Insights/Next Move format focused on the current client
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 NoteAgent [Customer {client_id}]: Starting client notes analysis")
        logger.info(f"📊 NoteAgent [Customer {client_id}]: Received {len(notes_data)} total notes")
        logger.info(f"🎯 NoteAgent [Customer {client_id}]: Analysis focus: {analysis_focus}, Employee filter: {employee_id}")

        # Filter notes for the current client only
        client_notes = [
            note for note in notes_data
            if note.get('client_id') == client_id
        ]

        logger.info(f"📊 NoteAgent [Customer {client_id}]: Found {len(client_notes)} notes for this client")

        if not client_notes:
            logger.warning(f"⚠️ NoteAgent [Customer {client_id}]: No notes found for this client")
            return {
                "error": f"No notes found for client_id {client_id}",
                "client_id": client_id
            }

        formatted_data = self.format_notes_for_analysis(client_notes, context=f"note_analysis_for_client_{client_id}")

        # Get most recent note summary for current client
        recent_note_summary = self._get_most_recent_note_summary(client_notes, employee_id, client_id)

        focus_prompts = {
            "comprehensive": """REQUIRED JSON OUTPUT FORMAT:
{
  "client_id": 123,
  "activities": [
    {
      "type": "note",
      "date": "YYYY-MM-DD",
      "title": "Note title",
      "content_summary": "Brief summary of note content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Note Patterns",
      "insight": "Three sentence insight about note-taking patterns and frequency. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Content Analysis",
      "insight": "Three sentence insight about note content themes and topics. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Relationship Health",
      "insight": "Three sentence insight about relationship status based on notes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_note_summary": {
    "has_recent_note": true/false,
    "note_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "note_title": "Title of most recent note",
    "content_preview": "First 150 characters of note content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent note"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Specific recommended action",
    "rationale": "Why this action is recommended"
  }
}"""
        }

        system_message = f"""You are an expert client relationship analyst. You MUST return valid JSON in the exact format specified.

CRITICAL REQUIREMENTS:
1. Each insight must contain exactly 3 sentences
2. Activity status must be 'active' if note is <7 days old, 'inactive' if >7 days old, 'decline' if no recent notes
3. Return only valid JSON - no additional text or formatting
4. Use the actual note data provided to populate activities and insights

Focus on {analysis_focus} analysis of the client notes."""

        prompt = f"""Analyze the following client note data and return structured JSON:

{formatted_data}

{focus_prompts.get(analysis_focus, focus_prompts['comprehensive'])}

IMPORTANT:
- Return ONLY valid JSON in the specified format
- Each insight must be exactly 3 sentences
- Use actual dates and content from the note data
- Determine activity status based on note timestamps"""

        response = self._generate_content(prompt, system_message)

        try:
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            result = json.loads(response_clean)

            # Add recent note summary to the result
            if recent_note_summary['has_recent_note']:
                formatted_date = self._format_date_safely(recent_note_summary['note_date'])
                result['recent_note_summary'] = {
                    "has_recent_note": True,
                    "note_date": formatted_date,
                    "employee_id": recent_note_summary['employee_id'],
                    "client_id": recent_note_summary['client_id'],
                    "note_title": recent_note_summary['note_title'],
                    "content_preview": recent_note_summary['content_preview'],
                    "status": recent_note_summary['status'],
                    "key_points": f"Most recent note from {formatted_date}: {recent_note_summary['note_title']} - {recent_note_summary['content_preview']}"
                }
            else:
                result['recent_note_summary'] = {
                    "has_recent_note": False,
                    "message": recent_note_summary.get('message', 'No recent note found')
                }

            return result

        except json.JSONDecodeError:
            # Fallback structured response if JSON parsing fails
            fallback_result = {
                "client_id": client_id,
                "activities": [
                    {
                        "type": "note",
                        "date": self._format_date_safely(client_notes[0].get('created_at', '')) if client_notes else "N/A",
                        "title": "Note analysis",
                        "content_summary": "Client note analysis",
                        "status": self._determine_activity_status(client_notes[0].get('created_at') if client_notes else None)
                    }
                ],
                "insights": [
                    {
                        "category": "Analysis Status",
                        "insight": "Note analysis was requested but encountered processing challenges. The system attempted to analyze the provided client notes. Manual review of the note content may be needed for detailed insights."
                    }
                ],
                "next_move": {
                    "priority": "medium",
                    "action": "Review client notes manually",
                    "rationale": "Automated analysis encountered issues, manual review recommended"
                }
            }

            # Add recent note summary to fallback result
            if recent_note_summary['has_recent_note']:
                formatted_date = self._format_date_safely(recent_note_summary['note_date'])
                fallback_result['recent_note_summary'] = {
                    "has_recent_note": True,
                    "note_date": formatted_date,
                    "employee_id": recent_note_summary['employee_id'],
                    "client_id": recent_note_summary['client_id'],
                    "note_title": recent_note_summary['note_title'],
                    "content_preview": recent_note_summary['content_preview'],
                    "status": recent_note_summary['status'],
                    "key_points": f"Most recent note from {formatted_date}: {recent_note_summary['note_title']} - {recent_note_summary['content_preview']}"
                }
            else:
                fallback_result['recent_note_summary'] = {
                    "has_recent_note": False,
                    "message": recent_note_summary.get('message', 'No recent note found')
                }

            return fallback_result

    def generate_note_insights(self,
                             notes_data: List[Dict[str, Any]],
                             client_id: int,
                             insight_type: str = "strategic",
                             employee_id: int = None) -> Dict[str, Any]:
        """
        Generate specific insights from note data for a specific current client with structured JSON output format

        Args:
            notes_data: List of note records
            client_id: Current client ID to focus analysis on (REQUIRED)
            insight_type: Type of insights ("strategic", "tactical", "relationship", "content")
            employee_id: Optional specific employee ID to filter by

        Returns:
            Structured JSON with Activities/Insights/Next Move format focused on the current client
        """
        # Filter notes for the current client only
        client_notes = [
            note for note in notes_data
            if note.get('client_id') == client_id
        ]

        if not client_notes:
            return {
                "error": f"No notes found for client_id {client_id}",
                "client_id": client_id
            }

        formatted_data = self.format_notes_for_analysis(client_notes, context=f"note_insights_generation_for_client_{client_id}")

        # Get most recent note summary for current client
        recent_note_summary = self._get_most_recent_note_summary(client_notes, employee_id, client_id)

        insight_prompts = {
            "strategic": """REQUIRED JSON OUTPUT FORMAT:
{
  "client_id": 123,
  "activities": [
    {
      "type": "note",
      "date": "YYYY-MM-DD",
      "title": "Note title",
      "content_summary": "Brief summary of note content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Strategic Note Opportunities",
      "insight": "Three sentence insight about strategic opportunities identified in client notes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Relationship Development",
      "insight": "Three sentence insight about relationship building through note documentation. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Business Impact Assessment",
      "insight": "Three sentence insight about business impact documented in notes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_note_summary": {
    "has_recent_note": true/false,
    "note_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "note_title": "Title of most recent note",
    "content_preview": "First 150 characters of note content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent note"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Strategic action based on note analysis",
    "rationale": "Strategic reasoning for recommended action"
  }
}""",

            "tactical": """REQUIRED JSON OUTPUT FORMAT:
{
  "client_id": 123,
  "activities": [
    {
      "type": "note",
      "date": "YYYY-MM-DD",
      "title": "Note title",
      "content_summary": "Brief summary of note content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Immediate Action Items",
      "insight": "Three sentence insight about immediate actions needed based on notes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Process Improvements",
      "insight": "Three sentence insight about process improvements identified from note patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Client Service Optimization",
      "insight": "Three sentence insight about optimizing client service based on notes. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_note_summary": {
    "has_recent_note": true/false,
    "note_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "note_title": "Title of most recent note",
    "content_preview": "First 150 characters of note content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent note"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Tactical action for immediate implementation",
    "rationale": "Tactical reasoning for recommended action"
  }
}""",

            "relationship": """REQUIRED JSON OUTPUT FORMAT:
{
  "client_id": 123,
  "activities": [
    {
      "type": "note",
      "date": "YYYY-MM-DD",
      "title": "Note title",
      "content_summary": "Brief summary of note content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Relationship Health",
      "insight": "Three sentence insight about current relationship health based on note content and frequency. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Client Engagement Levels",
      "insight": "Three sentence insight about client engagement levels and interaction patterns. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Trust and Communication Indicators",
      "insight": "Three sentence insight about trust and communication indicators in note documentation. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_note_summary": {
    "has_recent_note": true/false,
    "note_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "note_title": "Title of most recent note",
    "content_preview": "First 150 characters of note content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent note"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Relationship-focused action",
    "rationale": "Relationship-based reasoning for recommended action"
  }
}""",

            "content": """REQUIRED JSON OUTPUT FORMAT:
{
  "client_id": 123,
  "activities": [
    {
      "type": "note",
      "date": "YYYY-MM-DD",
      "title": "Note title",
      "content_summary": "Brief summary of note content",
      "status": "active/inactive/decline"
    }
  ],
  "insights": [
    {
      "category": "Note Content Themes",
      "insight": "Three sentence insight about recurring themes and topics in note content. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Information Quality",
      "insight": "Three sentence insight about quality and completeness of information documented. Each insight must contain exactly three sentences. This provides proper structure and readability."
    },
    {
      "category": "Documentation Effectiveness",
      "insight": "Three sentence insight about effectiveness of note-taking and documentation practices. Each insight must contain exactly three sentences. This provides proper structure and readability."
    }
  ],
  "recent_note_summary": {
    "has_recent_note": true/false,
    "note_date": "YYYY-MM-DD",
    "employee_id": 123,
    "client_id": 456,
    "note_title": "Title of most recent note",
    "content_preview": "First 150 characters of note content...",
    "status": "active/inactive/decline",
    "key_points": "Summary of main points from the most recent note"
  },
  "next_move": {
    "priority": "high/medium/low",
    "action": "Content-focused improvement action",
    "rationale": "Content-based reasoning for recommended action"
  }
}"""
        }

        system_message = f"""You are an expert client relationship analyst. You MUST return valid JSON in the exact format specified.

CRITICAL REQUIREMENTS:
1. Each insight must contain exactly 3 sentences
2. Activity status must be 'active' if note is <7 days old, 'inactive' if >7 days old, 'decline' if no recent notes
3. Return only valid JSON - no additional text or formatting
4. Use the actual note data provided to populate activities and insights

Focus on {insight_type} insights from the client notes."""

        prompt = f"""Generate {insight_type} insights from the following client note data and return structured JSON:

{formatted_data}

{insight_prompts.get(insight_type, insight_prompts['strategic'])}

IMPORTANT:
- Return ONLY valid JSON in the specified format
- Each insight must be exactly 3 sentences
- Use actual dates and content from the note data
- Determine activity status based on note timestamps"""

        response = self._generate_content(prompt, system_message)

        try:
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            result = json.loads(response_clean)

            # Add recent note summary to the result
            if recent_note_summary['has_recent_note']:
                formatted_date = self._format_date_safely(recent_note_summary['note_date'])
                result['recent_note_summary'] = {
                    "has_recent_note": True,
                    "note_date": formatted_date,
                    "employee_id": recent_note_summary['employee_id'],
                    "client_id": recent_note_summary['client_id'],
                    "note_title": recent_note_summary['note_title'],
                    "content_preview": recent_note_summary['content_preview'],
                    "status": recent_note_summary['status'],
                    "key_points": f"Most recent note from {formatted_date}: {recent_note_summary['note_title']} - {recent_note_summary['content_preview']}"
                }
            else:
                result['recent_note_summary'] = {
                    "has_recent_note": False,
                    "message": recent_note_summary.get('message', 'No recent note found')
                }

            return result

        except json.JSONDecodeError:
            # Fallback structured response if JSON parsing fails
            fallback_result = {
                "client_id": client_id,
                "activities": [
                    {
                        "type": "note",
                        "date": self._format_date_safely(note.get('created_at', '')) if client_notes else "N/A",
                        "title": f"Note {insight_type} analysis",
                        "content_summary": f"Client note {insight_type} analysis",
                        "status": self._determine_activity_status(client_notes[0].get('created_at') if client_notes else None)
                    }
                ],
                "insights": [
                    {
                        "category": f"{insight_type.title()} Analysis",
                        "insight": f"Note {insight_type} analysis was requested but encountered processing challenges. The system attempted to analyze the provided client notes for {insight_type} insights. Manual review of the note content may be needed for detailed {insight_type} assessment."
                    }
                ],
                "next_move": {
                    "priority": "medium",
                    "action": f"Review client notes for {insight_type} insights",
                    "rationale": f"Automated {insight_type} analysis encountered issues, manual review recommended"
                }
            }

            # Add recent note summary to fallback result
            if recent_note_summary['has_recent_note']:
                formatted_date = self._format_date_safely(recent_note_summary['note_date'])
                fallback_result['recent_note_summary'] = {
                    "has_recent_note": True,
                    "note_date": formatted_date,
                    "employee_id": recent_note_summary['employee_id'],
                    "client_id": recent_note_summary['client_id'],
                    "note_title": recent_note_summary['note_title'],
                    "content_preview": recent_note_summary['content_preview'],
                    "status": recent_note_summary['status'],
                    "key_points": f"Most recent note from {formatted_date}: {recent_note_summary['note_title']} - {recent_note_summary['content_preview']}"
                }
            else:
                fallback_result['recent_note_summary'] = {
                    "has_recent_note": False,
                    "message": recent_note_summary.get('message', 'No recent note found')
                }

            return fallback_result
