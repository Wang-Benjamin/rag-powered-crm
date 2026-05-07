"""
AI Service for CSV mapping service.

This service is designed to work as a pure Python library with optional AI capabilities.
All AI integrations are optional and can be disabled or unavailable without affecting core functionality.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Callable
from ..models.mapping_models import MappingConfig

logger = logging.getLogger(__name__)


class AIServiceManager:
    """Enhanced AI service manager for column mapping with OpenAI provider.

    This class provides optional AI capabilities for column mapping. It can operate
    in "no-AI" mode gracefully when API keys are not provided or AI libraries
    are not available.
    """
    
    def __init__(
        self,
        config: MappingConfig = None,
        openai_api_key: Optional[str] = None,
        openai_client: Optional[Any] = None,
        fallback_strategy: Optional[Callable[[List[str], List[str], str], Dict[str, Any]]] = None
    ):
        """Initialize AI service manager with optional AI capabilities.

        Args:
            config: Mapping configuration
            openai_api_key: Optional OpenAI API key
            openai_client: Optional pre-configured OpenAI client
            fallback_strategy: Optional custom fallback function when AI is unavailable
        """
        self.config = config or MappingConfig()
        self._openai_api_key = openai_api_key
        self._openai_client = openai_client
        self._fallback_strategy = fallback_strategy

        # Track availability of AI libraries
        self._openai_available = self._check_openai_availability()

        # Log initialization status
        self._log_ai_status()
    
    def _check_openai_availability(self) -> bool:
        """Check if OpenAI library is available and can be used."""
        try:
            import openai
            return True
        except ImportError:
            logger.debug("OpenAI library not available")
            return False
    
    def _log_ai_status(self) -> None:
        """Log the current AI service availability status."""
        available_services = []

        if self.is_openai_available():
            available_services.append("OpenAI")

        if available_services:
            logger.info(f"AI services available: {', '.join(available_services)}")
        else:
            logger.info("No AI services available - operating in fallback mode")
    
    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self._openai_api_key
    
    @property
    def openai_client(self):
        """Get or create OpenAI client if available."""
        if self._openai_client is not None:
            return self._openai_client
            
        if not self._openai_available or not self.openai_api_key:
            return None
            
        try:
            import openai
            self._openai_client = openai.AsyncOpenAI(
                api_key=self.openai_api_key,
                timeout=120.0
            )
            logger.debug("OpenAI client initialized")
            return self._openai_client
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return None
    
    def is_openai_available(self) -> bool:
        """Check if OpenAI API is available and configured."""
        return (
            self._openai_available and 
            bool(self.openai_api_key) and
            self.openai_client is not None
        )
    
    def is_any_ai_available(self) -> bool:
        """Check if any AI service is available."""
        return self.is_openai_available()
    
    def get_ai_capabilities(self) -> Dict[str, Any]:
        """Get detailed information about AI capabilities."""
        return {
            "ai_enabled": self.is_any_ai_available(),
            "openai_available": self.is_openai_available(),
            "libraries_available": {
                "openai": self._openai_available
            },
            "api_keys_configured": {
                "openai": bool(self.openai_api_key)
            },
            "fallback_strategy": self._fallback_strategy is not None
        }
    
    async def analyze_column_mappings(
        self, 
        source_columns: List[str], 
        target_schema: List[str],
        service_context: str = "generic"
    ) -> Dict[str, Any]:
        """
        Use AI to analyze and suggest column mappings with enhanced context.
        
        This method gracefully falls back to non-AI strategies when AI is unavailable.
        
        Args:
            source_columns: List of source column names
            target_schema: List of target column names
            service_context: Domain context ('sales', 'crm', 'employee', etc.)
            
        Returns:
            Dictionary with mapping suggestions and metadata
        """
        
        # Check if AI is available
        if not self.is_any_ai_available():
            logger.info("AI services not available, using fallback strategy")
            return self._get_fallback_mappings(source_columns, target_schema, service_context)
        
        # Build context-aware prompt
        mapping_prompt = self._build_mapping_prompt(
            source_columns, target_schema, service_context
        )
        
        # Try OpenAI
        if self.is_openai_available():
            try:
                response = await self.call_openai(mapping_prompt, json_output=True)
                if response:
                    result = self._parse_ai_mapping_response(response, source_columns, target_schema)
                    if result.get("mappings"):  # Check if we got meaningful results
                        return result
            except Exception as e:
                logger.warning(f"OpenAI mapping failed: {e}")

        # Final fallback to non-AI strategy
        logger.warning("AI services failed, using fallback strategy")
        return self._get_fallback_mappings(source_columns, target_schema, service_context)
    
    def _get_fallback_mappings(
        self, 
        source_columns: List[str], 
        target_schema: List[str], 
        service_context: str
    ) -> Dict[str, Any]:
        """
        Generate basic column mappings without AI.
        
        This method uses simple heuristics for column matching when AI is not available.
        """
        
        # Use custom fallback strategy if provided
        if self._fallback_strategy:
            try:
                return self._fallback_strategy(source_columns, target_schema, service_context)
            except Exception as e:
                logger.error(f"Custom fallback strategy failed: {e}")
        
        # Default fallback: exact name matching and simple heuristics
        mappings = []
        mapped_targets = set()
        
        for source_col in source_columns:
            source_lower = source_col.lower().strip()
            best_match = None
            confidence = 0
            
            # Try exact match first
            for target_col in target_schema:
                target_lower = target_col.lower().strip()
                
                if source_lower == target_lower:
                    best_match = target_col
                    confidence = 95
                    break
                
                # Try simple substring matching
                if source_lower in target_lower or target_lower in source_lower:
                    if confidence < 70:
                        best_match = target_col
                        confidence = 70
                
                # Try common patterns
                patterns = [
                    (source_lower.replace('_', ''), target_lower.replace('_', '')),
                    (source_lower.replace('-', ''), target_lower.replace('-', '')),
                    (source_lower.replace(' ', ''), target_lower.replace(' ', ''))
                ]
                
                for s_pattern, t_pattern in patterns:
                    if s_pattern == t_pattern and confidence < 80:
                        best_match = target_col
                        confidence = 80
            
            # Only add mappings above threshold and avoid duplicates
            if best_match and confidence >= 60 and best_match not in mapped_targets:
                mappings.append({
                    "source_column": source_col,
                    "target_column": best_match,
                    "confidence": confidence,
                    "reasoning": f"Pattern-based matching (confidence: {confidence}%)",
                    "mapping_type": "pattern"
                })
                mapped_targets.add(best_match)
        
        # Calculate unmapped columns
        mapped_sources = {m["source_column"] for m in mappings}
        unmapped_sources = [col for col in source_columns if col not in mapped_sources]
        unmapped_targets = [col for col in target_schema if col not in mapped_targets]
        
        # Calculate overall confidence
        if mappings:
            overall_confidence = sum(m["confidence"] for m in mappings) / len(mappings)
        else:
            overall_confidence = 0
        
        return {
            "mappings": mappings,
            "overall_confidence": overall_confidence,
            "ai_provider": "fallback_heuristics",
            "unmapped_sources": unmapped_sources,
            "unmapped_targets": unmapped_targets,
            "service_context": service_context,
            "ai_available": False
        }
    
    def _build_mapping_prompt(
        self, 
        source_columns: List[str], 
        target_schema: List[str], 
        service_context: str
    ) -> str:
        """Build context-aware mapping prompt for AI."""
        
        context_descriptions = {
            "sales": "sales data including revenue, employee performance, locations, and customers",
            "crm": "customer relationship management data with contacts, interactions, and deals",
            "employee": "employee data including profiles, performance, skills, and assignments",
            "lead-gen": "lead generation data with prospects, companies, and contact information",
            "generic": "business data"
        }
        
        context_desc = context_descriptions.get(service_context, "business data")
        
        # Domain-specific mapping hints
        domain_hints = ""
        if service_context == "sales":
            domain_hints = """
Common sales mappings to consider:
- Revenue/sales amounts: 'revenue', 'sales_amount', 'total_sales', 'amount'
- Employee names: 'employee_name', 'salesrep_name', 'rep_name', 'salesperson'
- Locations: 'location', 'region', 'territory', 'state', 'province'
- Customers: 'customer_name', 'client', 'account'
- Quantities: 'quantity_sold', 'total_quantity', 'units'
"""
        elif service_context == "crm":
            domain_hints = """
Common CRM mappings to consider:
- Contact info: 'email', 'phone', 'contact_email', 'phone_number'
- Names: 'first_name', 'last_name', 'full_name', 'contact_name'
- Companies: 'company', 'organization', 'account_name'
- Dates: 'created_date', 'last_contact', 'updated_at'
"""
        
        prompt = f"""
You are an expert data analyst specializing in column mapping for {context_desc}.

Analyze these columns for semantic mapping:

Source columns: {json.dumps(source_columns)}
Target schema: {json.dumps(target_schema)}

{domain_hints}

For each source column, determine:
1. The best target column match (or null if no good match exists)
2. Confidence score (0-100) based on semantic similarity
3. Clear reasoning for the mapping decision
4. Mapping type: "exact", "semantic_ai", or "pattern"

Consider:
- Semantic meaning over exact text matching
- Business domain context ({service_context})
- Common abbreviations and synonyms
- Data type compatibility

Return JSON in this exact format:
{{
  "mappings": [
    {{
      "source_column": "total_revenue",
      "target_column": "sales_amount", 
      "confidence": 92,
      "reasoning": "Both represent monetary sales values - semantically equivalent",
      "mapping_type": "semantic_ai"
    }}
  ],
  "overall_confidence": 85,
  "ai_provider": "analysis_model",
  "unmapped_sources": [],
  "unmapped_targets": []
}}

Only suggest mappings with confidence >= 60. Be conservative with confidence scores.
"""
        
        return prompt
    
    async def call_openai(self, prompt: str, json_output: bool = True) -> Optional[str]:
        """Enhanced OpenAI API call with retry logic."""
        if not self.openai_client:
            logger.error("OpenAI client not available")
            return None
        
        for attempt in range(self.config.max_ai_retries + 1):
            try:
                messages = [{"role": "user", "content": prompt}]
                
                if json_output:
                    response = await self.openai_client.chat.completions.create(
                        model=self.config.ai_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        timeout=10.0,  # Reduced from 120s to 10s for faster failure
                        temperature=0.1  # Low temperature for consistent mapping
                    )
                else:
                    response = await self.openai_client.chat.completions.create(
                        model=self.config.ai_model,
                        messages=messages,
                        timeout=10.0,  # Reduced from 120s to 10s for faster failure
                        temperature=0.1
                    )
                
                content = response.choices[0].message.content
                if content:
                    return content
                    
            except Exception as e:
                logger.warning(f"OpenAI attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_ai_retries:
                    logger.error(f"OpenAI API call failed after {self.config.max_ai_retries + 1} attempts")
                    return None
        
        return None
    
    def _parse_ai_mapping_response(
        self, 
        response: str, 
        source_columns: List[str], 
        target_schema: List[str]
    ) -> Dict[str, Any]:
        """Parse and validate AI mapping response."""
        try:
            data = json.loads(response) if isinstance(response, str) else response
            
            # Ensure required fields exist
            if "mappings" not in data:
                data["mappings"] = []
            
            # Validate and clean mappings
            valid_mappings = []
            for mapping in data.get("mappings", []):
                if self._validate_mapping(mapping, source_columns, target_schema):
                    valid_mappings.append(mapping)
            
            data["mappings"] = valid_mappings
            data["ai_provider"] = data.get("ai_provider", "openai")
            data["ai_available"] = True
            
            # Calculate unmapped columns if not provided
            if "unmapped_sources" not in data:
                mapped_sources = {m["source_column"] for m in valid_mappings}
                data["unmapped_sources"] = [col for col in source_columns if col not in mapped_sources]
            
            if "unmapped_targets" not in data:
                mapped_targets = {m["target_column"] for m in valid_mappings if m["target_column"]}
                data["unmapped_targets"] = [col for col in target_schema if col not in mapped_targets]
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse AI mapping response: {e}")
            return {
                "mappings": [],
                "overall_confidence": 0,
                "ai_provider": "failed",
                "ai_available": True,
                "error": f"Parse error: {str(e)}"
            }
    
    def _validate_mapping(self, mapping: Dict[str, Any], source_columns: List[str], target_schema: List[str]) -> bool:
        """Validate a single mapping from AI response."""
        required_fields = ["source_column", "confidence"]
        
        # Check required fields
        for field in required_fields:
            if field not in mapping:
                logger.warning(f"Mapping missing required field: {field}")
                return False
        
        # Validate source column exists
        if mapping["source_column"] not in source_columns:
            logger.warning(f"Invalid source column: {mapping['source_column']}")
            return False
        
        # Validate target column exists (if provided)
        target_col = mapping.get("target_column")
        if target_col and target_col not in target_schema:
            logger.warning(f"Invalid target column: {target_col}")
            return False
        
        # Validate confidence range
        confidence = mapping.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
            logger.warning(f"Invalid confidence score: {confidence}")
            return False
        
        return True


def create_ai_service(
    openai_api_key: Optional[str] = None,
    config: Optional[MappingConfig] = None,
    fallback_strategy: Optional[Callable[[List[str], List[str], str], Dict[str, Any]]] = None
) -> AIServiceManager:
    """
    Factory function to create an AI service manager with optional configurations.

    This function provides a convenient way to create an AI service manager
    without requiring any specific dependencies to be available.

    Args:
        openai_api_key: Optional OpenAI API key
        config: Optional mapping configuration
        fallback_strategy: Optional custom fallback function

    Returns:
        Configured AIServiceManager instance
    """
    return AIServiceManager(
        config=config,
        openai_api_key=openai_api_key,
        fallback_strategy=fallback_strategy
    )