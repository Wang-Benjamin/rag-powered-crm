"""
AI Model Factory - Centralized Model Initialization for CRM Agents

A centralized factory for initializing AI models (OpenAI) used by all CRM agents.
This eliminates code duplication and provides a single point of configuration for model initialization.

Key Features:
1. Centralized model initialization for OpenAI
2. Consistent API key management from environment variables
3. Default model configuration with environment variable overrides
4. Comprehensive error handling and logging
5. Reusable across all CRM agent classes

Supported Providers:
- OpenAI (gpt-4o, gpt-4.1-mini, gpt-4-turbo)

Usage:
    from agents.model_factory import ModelFactory

    # Initialize factory
    factory = ModelFactory(provider="openai", model_name="gpt-4.1-mini")

    # Get initialized model and client
    model_info = factory.get_model_info()
    client = model_info.client  # For OpenAI
"""

import openai
import os
import logging
from typing import Optional, Union, NamedTuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ModelInfo(NamedTuple):
    """Container for model initialization information"""
    provider: str
    model_name: str
    client: Optional[openai.OpenAI] = None


class ModelFactory:
    """
    Centralized factory for AI model initialization

    This factory handles the initialization of AI models for all CRM agents,
    eliminating code duplication and providing consistent configuration.
    """

    # Default models for each provider
    DEFAULT_MODELS = {
        "openai": "gpt-4.1-mini"
    }

    # Supported providers
    SUPPORTED_PROVIDERS = {"openai"}

    def __init__(self,
                 provider: str = "openai",
                 model_name: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 agent_name: str = "Unknown Agent"):
        """
        Initialize the Model Factory

        Args:
            provider: AI provider to use ("openai")
            model_name: Specific model to use (if None, uses defaults)
            openai_api_key: OpenAI API key (if not provided, uses environment variable)
            agent_name: Name of the agent using this factory (for logging)
        """
        self.provider = provider.lower()
        self.agent_name = agent_name

        # Validate provider
        if self.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}. Use one of: {', '.join(self.SUPPORTED_PROVIDERS)}")

        # Set model name with defaults
        self.model_name = self._resolve_model_name(model_name)

        # Store API keys
        self.openai_api_key = openai_api_key

        # Initialize the model
        self.model_info = self._initialize_model()

    def _resolve_model_name(self, model_name: Optional[str]) -> str:
        """
        Resolve the model name using defaults and environment variables

        Args:
            model_name: Provided model name or None

        Returns:
            Resolved model name
        """
        if model_name is not None:
            return model_name

        # Check environment variables first
        if self.provider == "openai":
            return os.getenv("DEFAULT_OPENAI_MODEL", self.DEFAULT_MODELS["openai"])

        # Fallback to hardcoded defaults
        return self.DEFAULT_MODELS.get(self.provider, "gpt-4.1-mini")

    def _initialize_model(self) -> ModelInfo:
        """
        Initialize the AI model based on the provider

        Returns:
            ModelInfo containing the initialized model/client
        """
        if self.provider == "openai":
            return self._init_openai()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _init_openai(self) -> ModelInfo:
        """
        Initialize OpenAI model
        
        Returns:
            ModelInfo with OpenAI client
        """
        # Handle API key
        api_key = self.openai_api_key
        if api_key:
            openai.api_key = api_key
        elif os.environ.get("OPENAI_API_KEY"):
            openai.api_key = os.environ["OPENAI_API_KEY"]
        else:
            raise ValueError(
                "OpenAI API key must be provided either as parameter or OPENAI_API_KEY environment variable"
            )
        
        # Create client
        try:
            client = openai.OpenAI(api_key=openai.api_key)
            
            logger.info(f"✅ Initialized {self.agent_name} with OpenAI {self.model_name}")
            
            return ModelInfo(
                provider=self.provider,
                model_name=self.model_name,
                client=client
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client for {self.agent_name}: {str(e)}")
            raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def get_model_info(self) -> ModelInfo:
        """
        Get the initialized model information
        
        Returns:
            ModelInfo containing provider, model_name, and initialized client/model
        """
        return self.model_info
    
    def generate_content(self, prompt: str, system_message: Optional[str] = None) -> str:
        """
        Generate content using the initialized model

        Args:
            prompt: The user prompt
            system_message: Optional system message for better context

        Returns:
            Generated content string
        """
        if system_message is None:
            system_message = "You are a helpful AI assistant."

        try:
            response = self.model_info.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating content with {self.provider} for {self.agent_name}: {str(e)}")
            return f"Error generating content with {self.provider}: {str(e)}"

    @classmethod
    def create_for_agent(cls,
                        agent_name: str,
                        provider: str = "openai",
                        model_name: Optional[str] = None,
                        openai_api_key: Optional[str] = None) -> 'ModelFactory':
        """
        Factory method to create a ModelFactory for a specific agent

        Args:
            agent_name: Name of the agent
            provider: AI provider to use
            model_name: Specific model to use
            openai_api_key: OpenAI API key

        Returns:
            Configured ModelFactory instance
        """
        return cls(
            provider=provider,
            model_name=model_name,
            openai_api_key=openai_api_key,
            agent_name=agent_name
        )
