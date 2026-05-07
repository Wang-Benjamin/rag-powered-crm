"""AI Connection Manager for CRM Service."""

import os
import logging
from typing import Optional, Dict, Any
import openai

from config.settings import settings
from utils.exceptions import AIServiceException

logger = logging.getLogger(__name__)


class AIConnectionManager:
    """Manages AI service connections and interactions."""

    def __init__(self):
        self.client = None
        self.model_name = "gpt-4.1-mini"
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the AI client."""
        try:
            # Initialize OpenAI client
            api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
            if not api_key:
                logger.warning("No OpenAI API key found")
                return

            self.client = openai.OpenAI(api_key=api_key)
            logger.info("AI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            raise AIServiceException(f"Failed to initialize AI service: {e}")
    
    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate content using the AI model."""
        if not self.client:
            raise AIServiceException("AI client not initialized")

        try:
            messages = [
                {"role": "system", "content": system_instruction or "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to generate content: {e}")
            raise AIServiceException(f"Failed to generate content: {e}")
    
    def generate_email(
        self,
        customer_info: Dict[str, Any],
        email_type: str,
        context: str,
        interactions: Optional[str] = None
    ) -> str:
        """Generate an email using AI."""
        system_instruction = """You are a professional email writer for a CRM system. 
        Write personalized, professional emails based on the context provided.
        Keep emails concise, friendly, and action-oriented."""
        
        prompt = f"""
        Generate a {email_type} email for the following customer:
        
        Customer Information:
        - Name: {customer_info.get('name', 'Customer')}
        - Company: {customer_info.get('company', 'N/A')}
        - Position: {customer_info.get('position', 'N/A')}

        Email Context:
        {context}
        
        Previous Interactions:
        {interactions or 'No previous interactions'}
        
        Please write a professional email that:
        1. Is personalized to the customer
        2. References relevant context
        3. Has a clear call to action
        4. Maintains a professional but friendly tone
        """
        
        return self.generate_content(prompt, system_instruction)
    
    def generate_analytics_insights(
        self,
        data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> str:
        """Generate analytics insights using AI."""
        system_instruction = """You are a business analyst providing insights for a CRM system.
        Analyze the data provided and generate actionable insights."""
        
        prompt = f"""
        Analyze the following CRM data and provide {analysis_type} insights:
        
        {data}
        
        Please provide:
        1. Key observations
        2. Trends and patterns
        3. Actionable recommendations
        4. Areas of concern or opportunity
        """
        
        return self.generate_content(prompt, system_instruction)
    
    def generate_todo_items(
        self,
        customer_info: Dict[str, Any],
        interactions: Optional[str] = None
    ) -> str:
        """Generate todo items for customer follow-up."""
        system_instruction = """You are a CRM assistant helping sales teams manage customer relationships.
        Generate specific, actionable todo items based on customer information and interactions."""
        
        prompt = f"""
        Generate todo items for following up with this customer:
        
        Customer Information:
        - Name: {customer_info.get('name', 'Customer')}
        - Company: {customer_info.get('company', 'N/A')}
        - Status: {customer_info.get('status', 'prospect')}
        - Last Contact: {customer_info.get('last_contact_date', 'Unknown')}
        
        Previous Interactions:
        {interactions or 'No previous interactions'}
        
        Please generate 3-5 specific, actionable todo items with:
        1. Clear action to take
        2. Suggested timeline
        3. Priority level (High/Medium/Low)
        """
        
        return self.generate_content(prompt, system_instruction)
    
    def generate_interaction_summary(
        self,
        interaction_details: str
    ) -> str:
        """Generate a summary of customer interactions."""
        system_instruction = """You are a CRM assistant summarizing customer interactions.
        Create concise, informative summaries that highlight key points and action items."""
        
        prompt = f"""
        Summarize the following customer interaction:
        
        {interaction_details}
        
        Include:
        1. Key discussion points
        2. Decisions made
        3. Action items
        4. Next steps
        """
        
        return self.generate_content(prompt, system_instruction)


# Global AI manager instance
ai_manager = AIConnectionManager()


def get_ai_manager() -> AIConnectionManager:
    """FastAPI dependency to get AI manager."""
    return ai_manager