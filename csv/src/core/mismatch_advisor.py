"""
LLM Column Mismatch Advisor for CSV mapping service.

Provides intelligent, context-aware recommendations for handling column mismatches
during CSV append operations using AI models for business-context analysis.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple

from ..models.mismatch_models import (
    MismatchType, Severity, SuggestedAction, 
    ColumnMismatchRecommendation, BusinessContext
)
from ..utils.business_context import (
    infer_business_context, classify_extra_column, classify_missing_column,
    classify_type_mismatch, get_business_rationale, get_column_recommendation
)
from .ai_service import AIServiceManager

logger = logging.getLogger(__name__)

# Configuration constants
CACHE_TTL_SECONDS = 3600  # 1 hour
AI_FAILURE_THRESHOLD = 3  # Circuit breaker threshold
AI_CIRCUIT_TIMEOUT_SECONDS = 300  # 5 minutes
AI_OVERALL_TIMEOUT_SECONDS = 15  # Overall timeout for AI operations
FAST_PATH_COVERAGE_THRESHOLD = 0.8  # 80% coverage for fast-path optimization


class LLMColumnAdvisor:
    """
    AI-powered column advisor for intelligent CSV append recommendations.
    
    Provides business-context-aware analysis of column mismatches with:
    - Automated business domain inference
    - Context-aware recommendation generation
    - Confidence scoring and fallback mechanisms
    - Performance optimizations through caching
    
    This version works as a pure library accepting AI credentials as parameters
    rather than reading from environment variables.
    """
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        ai_service: Optional[AIServiceManager] = None
    ):
        """
        Initialize the LLM Column Advisor service.

        Args:
            openai_api_key: Optional OpenAI API key
            ai_service: Optional pre-configured AI service manager
        """

        # Initialize AI service
        if ai_service:
            self._ai_service = ai_service
        else:
            self._ai_service = AIServiceManager(
                openai_api_key=openai_api_key
            )
        
        # Cache management
        self._recommendation_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = CACHE_TTL_SECONDS

        # Circuit breaker for AI services
        self._ai_failure_count = 0
        self._ai_failure_threshold = AI_FAILURE_THRESHOLD
        self._ai_circuit_open_until = 0
        self._ai_circuit_timeout = AI_CIRCUIT_TIMEOUT_SECONDS

        logger.info("LLMColumnAdvisor service initialized")
    
    async def analyze_column_mismatches(
        self,
        csv_columns: List[str],
        table_columns: Dict[str, str],  # {column_name: data_type}
        table_name: str,
        extra_csv_columns: Optional[List[str]] = None,
        missing_table_columns: Optional[List[str]] = None,
        type_mismatches: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None
    ) -> List[ColumnMismatchRecommendation]:
        """
        Analyze column mismatches and provide intelligent recommendations.
        
        Args:
            csv_columns: List of columns in the CSV file
            table_columns: Dictionary of existing table columns and their types
            table_name: Name of the target table
            extra_csv_columns: Columns in CSV but not in table (optional, will calculate if not provided)
            missing_table_columns: Columns in table but not in CSV (optional, will calculate if not provided)
            type_mismatches: List of type mismatch details (optional, will calculate if not provided)
            schema_name: Schema name for additional context
            
        Returns:
            List of ColumnMismatchRecommendation objects
        """
        try:
            # Calculate mismatches if not provided (None means not provided, empty list means explicitly no mismatches)
            if extra_csv_columns is None:
                # First perform automatic column name matching for identical names
                automatically_matched_csv = set()
                for csv_col in csv_columns:
                    if csv_col in table_columns:
                        automatically_matched_csv.add(csv_col)
                
                # Only consider CSV columns as "extra" if they don't have automatic matches
                extra_csv_columns = [col for col in csv_columns if col not in automatically_matched_csv]
            
            if missing_table_columns is None:
                # First perform automatic column name matching for identical names
                automatically_matched_table = set()
                for csv_col in csv_columns:
                    if csv_col in table_columns:
                        automatically_matched_table.add(csv_col)
                
                # Only consider table columns as "missing" if they don't have automatic matches
                # Also exclude standard system columns
                missing_table_columns = [col for col in table_columns 
                                       if col not in automatically_matched_table 
                                       and col not in ['id', 'created_at', 'updated_at']]
            
            if type_mismatches is None:
                type_mismatches = []  # Would need actual CSV data to detect type mismatches
            
            # Early return if no actual mismatches to analyze
            if (not extra_csv_columns and not missing_table_columns and not type_mismatches):
                logger.info(f"No column mismatches found for table {table_name}, returning empty recommendations")
                return []
            
            # Infer business context
            business_context = infer_business_context(
                table_name, list(table_columns.keys()), csv_columns, schema_name
            )
            
            # Generate cache key
            cache_key = self._generate_cache_key(
                csv_columns, table_columns, table_name, extra_csv_columns, missing_table_columns
            )
            
            # Check cache
            cached_recommendations = self._get_from_cache(cache_key)
            if cached_recommendations is not None:
                logger.info(f"Retrieved cached recommendations for table {table_name}")
                return cached_recommendations
            
            # Generate recommendations
            recommendations = []
            
            # Try AI-powered analysis first (with circuit breaker)
            ai_recommendations = None
            if self._is_ai_circuit_closed():
                try:
                    ai_recommendations = await asyncio.wait_for(
                        self._generate_llm_recommendations(
                            csv_columns, table_columns, table_name, business_context,
                            extra_csv_columns, missing_table_columns, type_mismatches
                        ),
                        timeout=AI_OVERALL_TIMEOUT_SECONDS
                    )
                    self._reset_ai_circuit()  # Reset on success
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"AI recommendation generation failed/timed out: {e}")
                    self._record_ai_failure()
                    ai_recommendations = None
            else:
                logger.info("AI circuit breaker is open, skipping AI recommendations")
            
            if ai_recommendations:
                recommendations.extend(ai_recommendations)
                logger.info(f"Generated {len(ai_recommendations)} AI recommendations for table {table_name}")
            else:
                # Fallback to rule-based recommendations
                logger.info(f"AI unavailable, falling back to rule-based recommendations for table {table_name}")
                rule_based_recommendations = self._generate_rule_based_recommendations(
                    csv_columns, table_columns, table_name, business_context,
                    extra_csv_columns, missing_table_columns, type_mismatches
                )
                recommendations.extend(rule_based_recommendations)
            
            # Cache the results
            self._set_cache(cache_key, recommendations)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error analyzing column mismatches for table {table_name}: {e}")
            # Return basic rule-based recommendations as fallback
            return self._generate_rule_based_recommendations(
                csv_columns, table_columns, table_name, None,
                extra_csv_columns or [], missing_table_columns or [], type_mismatches or []
            )
    
    async def _generate_llm_recommendations(
        self,
        csv_columns: List[str],
        table_columns: Dict[str, str],
        table_name: str,
        business_context: Optional[BusinessContext],
        extra_csv_columns: List[str],
        missing_table_columns: List[str],
        type_mismatches: List[Dict[str, Any]]
    ) -> Optional[List[ColumnMismatchRecommendation]]:
        """Generate recommendations using LLM analysis."""
        
        if not self._ai_service.is_any_ai_available():
            logger.warning("No AI services available for LLM recommendations")
            return None
        
        try:
            # Fast path: Use rule-based recommendations for simple/common cases
            simple_recommendations = self._get_simple_recommendations(
                extra_csv_columns, missing_table_columns, table_name
            )
            
            # If all columns have simple rules, skip AI entirely
            total_columns = len(extra_csv_columns) + len(missing_table_columns)
            if len(simple_recommendations) == total_columns:
                logger.info(f"Using fast rule-based recommendations for all {len(simple_recommendations)} columns")
                return simple_recommendations

            # If we have mostly simple columns (80%+), use rule-based for all to avoid AI delay
            if total_columns > 0 and len(simple_recommendations) / total_columns >= FAST_PATH_COVERAGE_THRESHOLD:
                logger.info(f"Using rule-based recommendations for {len(simple_recommendations)}/{total_columns} columns (80%+ coverage)")
                # Generate rule-based recommendations for remaining columns too
                remaining_recommendations = self._generate_rule_based_recommendations(
                    csv_columns, table_columns, table_name, business_context,
                    [col for col in extra_csv_columns if not self._is_simple_column(col)],
                    [col for col in missing_table_columns if not self._is_simple_column(col)],
                    type_mismatches
                )
                return simple_recommendations + remaining_recommendations
            
            # Build optimized context-aware prompt for remaining complex cases
            complex_extra_columns = [col for col in extra_csv_columns if not self._is_simple_column(col)]
            complex_missing_columns = [col for col in missing_table_columns if not self._is_simple_column(col)]
            
            if not complex_extra_columns and not complex_missing_columns:
                return simple_recommendations
            
            prompt = self._build_optimized_analysis_prompt(
                csv_columns, table_columns, table_name, business_context,
                complex_extra_columns, complex_missing_columns, type_mismatches
            )
            
            # Try OpenAI with aggressive timeout
            if self._ai_service.is_openai_available():
                response_text = await self._ai_service.call_openai(prompt, json_output=True)
                if response_text:
                    try:
                        response_data = json.loads(response_text)
                        ai_recommendations = self._parse_llm_response(response_data)
                        if ai_recommendations:
                            return simple_recommendations + ai_recommendations
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse OpenAI JSON response: {e}")

            # If AI fails, return rule-based recommendations for all columns
            logger.warning("AI services failed or timed out, using rule-based recommendations")
            return self._generate_rule_based_recommendations(
                csv_columns, table_columns, table_name, business_context,
                extra_csv_columns, missing_table_columns, type_mismatches
            )
            
        except Exception as e:
            logger.error(f"Error generating LLM recommendations: {e}")
            return None
    
    def _build_optimized_analysis_prompt(
        self,
        csv_columns: List[str],
        table_columns: Dict[str, str],
        table_name: str,
        business_context: Optional[BusinessContext],
        extra_csv_columns: List[str],
        missing_table_columns: List[str],
        type_mismatches: List[Dict[str, Any]]
    ) -> str:
        """Build simplified prompt for faster LLM processing."""
        
        # Simplified context
        domain = business_context.domain if business_context else "general"
        
        prompt = f"""Analyze CSV column differences for {domain} table '{table_name}' (be concise):

Extra CSV columns: {extra_csv_columns}
Missing table columns: {missing_table_columns}

Return JSON with recommendations:
{{"recommendations": [
  {{"mismatch_type": "extra_csv"|"extra_table", "column_name": "...", "severity": "low"|"medium"|"high", 
    "recommendation": "Brief explanation (1 sentence)", "suggested_action": "add_column"|"ignore"|"manual_map", "confidence": 0.0-1.0}}
]}}"""
        
        return prompt
    
    def _is_simple_column(self, column_name: str) -> bool:
        """Check if column has obvious handling based on name patterns."""
        column_lower = column_name.lower()

        # Expanded patterns that don't need AI analysis
        simple_patterns = [
            # System/metadata columns
            'id', 'uuid', 'created_at', 'updated_at', 'deleted_at', 'timestamp', 'date', 'time',
            'version', 'status', 'active', 'enabled', 'deleted', 'visible', 'published',
            'created_by', 'updated_by', 'modified_by', 'deleted_by',
            'sort_order', 'position', 'rank', 'priority',

            # Common business columns
            'name', 'title', 'description', 'notes', 'comments',
            'email', 'phone', 'address', 'city', 'state', 'country',
            'zip', 'postal_code', 'website', 'url',

            # Numeric/financial columns
            'amount', 'price', 'cost', 'total', 'subtotal',
            'quantity', 'count', 'number', 'value', 'score'
        ]

        # Check for exact matches, contains, or common prefixes/suffixes
        pattern_match = any(pattern in column_lower for pattern in simple_patterns)

        # Check for common prefixes and suffixes
        prefix_suffix_match = (
            column_lower.startswith('is_') or
            column_lower.startswith('has_') or
            column_lower.startswith('can_') or
            column_lower.startswith('should_') or
            column_lower.endswith('_id') or
            column_lower.endswith('_date') or
            column_lower.endswith('_time') or
            column_lower.endswith('_at') or
            column_lower.endswith('_by') or
            column_lower.endswith('_count') or
            column_lower.endswith('_total') or
            column_lower.endswith('_amount')
        )

        # Generic patterns for custom/dynamic columns
        generic_pattern_match = (
            'col_' in column_lower or
            'field_' in column_lower or
            'column_' in column_lower or
            'data' in column_lower or
            'custom' in column_lower or
            'user_' in column_lower or
            'weird_' in column_lower or
            'special_' in column_lower or
            'extra_' in column_lower or
            'misc_' in column_lower or
            # Numbered fields like field_123, column_456
            (any(char.isdigit() for char in column_lower) and any(sep in column_lower for sep in ['_', '-']))
        )

        return pattern_match or prefix_suffix_match or generic_pattern_match
    
    def _get_simple_recommendations(
        self,
        extra_csv_columns: List[str],
        missing_table_columns: List[str],
        table_name: str
    ) -> List[ColumnMismatchRecommendation]:
        """Generate fast rule-based recommendations for simple/common column patterns."""
        recommendations = []

        for col in extra_csv_columns:
            if self._is_simple_column(col):
                # Determine appropriate action based on column type
                action, severity, recommendation = get_column_recommendation(col, "extra")
                recommendations.append(ColumnMismatchRecommendation(
                    mismatch_type=MismatchType.EXTRA_CSV,
                    column_name=col,
                    severity=getattr(Severity, severity.upper()),
                    recommendation=recommendation,
                    suggested_action=action,
                    confidence=0.95,
                    issue_type="extra"
                ))

        for col in missing_table_columns:
            if self._is_simple_column(col):
                # Determine appropriate action based on column type
                action, severity, recommendation = get_column_recommendation(col, "missing")
                recommendations.append(ColumnMismatchRecommendation(
                    mismatch_type=MismatchType.MISSING_TABLE,
                    column_name=col,
                    severity=getattr(Severity, severity.upper()),
                    recommendation=recommendation,
                    suggested_action=action,
                    confidence=0.90,
                    issue_type="missing"
                ))

        return recommendations
    
    def _parse_llm_response(self, response_data: Dict[str, Any]) -> List[ColumnMismatchRecommendation]:
        """Parse LLM response into recommendation objects."""
        recommendations = []
        
        try:
            # Handle different response formats
            recommendations_data = None
            
            if isinstance(response_data, dict):
                recommendations_data = response_data.get('recommendations', [])
            elif isinstance(response_data, list):
                recommendations_data = response_data
            else:
                logger.error(f"Unexpected response format: {type(response_data)}")
                return []
            
            if not recommendations_data:
                logger.warning("No recommendations data found in LLM response")
                return []
            
            for item in recommendations_data:
                try:
                    # Parse enums safely
                    mismatch_type = MismatchType(item.get('mismatch_type', 'extra_csv'))
                    severity = Severity(item.get('severity', 'medium'))
                    suggested_action = SuggestedAction(item.get('suggested_action', 'ignore'))
                    
                    # Validate confidence score
                    confidence = float(item.get('confidence', 0.5))
                    confidence = max(0.0, min(1.0, confidence))  # Clamp to valid range
                    
                    recommendation = ColumnMismatchRecommendation(
                        mismatch_type=mismatch_type,
                        column_name=item.get('column_name', ''),
                        severity=severity,
                        recommendation=item.get('recommendation', ''),
                        suggested_action=suggested_action,
                        confidence=confidence,
                        issue_type=item.get('issue_type', 'different'),
                        business_context=item.get('business_context'),
                        technical_details=item.get('technical_details'),
                        source_type=item.get('source_type'),
                        target_type=item.get('target_type')
                    )
                    
                    recommendations.append(recommendation)
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing individual recommendation: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(recommendations)} LLM recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []
    
    def _generate_rule_based_recommendations(
        self,
        csv_columns: List[str],
        table_columns: Dict[str, str],
        table_name: str,
        business_context: Optional[BusinessContext],
        extra_csv_columns: List[str],
        missing_table_columns: List[str],
        type_mismatches: List[Dict[str, Any]]
    ) -> List[ColumnMismatchRecommendation]:
        """Generate fallback recommendations using rule-based logic."""
        
        recommendations = []
        
        # Handle extra CSV columns
        for column in extra_csv_columns:
            severity_str, action, confidence = classify_extra_column(column, business_context)
            severity = getattr(Severity, severity_str.upper())
            
            recommendations.append(ColumnMismatchRecommendation(
                mismatch_type=MismatchType.EXTRA_CSV,
                column_name=column,
                severity=severity,
                recommendation=self._get_rule_based_recommendation(column, action, "extra_csv"),
                suggested_action=action,
                confidence=confidence,
                issue_type="extra",
                business_context=get_business_rationale(column, action, business_context)
            ))
        
        # Handle missing table columns
        for column in missing_table_columns:
            severity_str, confidence = classify_missing_column(column, business_context)
            severity = getattr(Severity, severity_str.upper())
            
            recommendations.append(ColumnMismatchRecommendation(
                mismatch_type=MismatchType.EXTRA_TABLE,
                column_name=column,
                severity=severity,
                recommendation=self._get_rule_based_recommendation(column, SuggestedAction.IGNORE, "missing"),
                suggested_action=SuggestedAction.IGNORE,
                confidence=confidence,
                issue_type="missing",
                business_context=f"Column {column} exists in table but not in CSV. Will use default values."
            ))
        
        # Handle type mismatches
        for mismatch in type_mismatches:
            column = mismatch.get('column', '')
            source_type = mismatch.get('source_type', '')
            target_type = mismatch.get('target_type', '')
            severity_str, action, confidence = classify_type_mismatch(source_type, target_type, business_context)
            severity = getattr(Severity, severity_str.upper())
            
            recommendations.append(ColumnMismatchRecommendation(
                mismatch_type=MismatchType.TYPE_MISMATCH,
                column_name=column,
                severity=severity,
                recommendation=self._get_rule_based_recommendation(column, action, "type_mismatch"),
                suggested_action=action,
                confidence=confidence,
                issue_type="different",
                business_context=get_business_rationale(column, action, business_context),
                source_type=source_type,
                target_type=target_type
            ))
        
        return recommendations
    
    def _get_rule_based_recommendation(
        self, 
        column: str, 
        action: SuggestedAction, 
        mismatch_type: str
    ) -> str:
        """Generate detailed rule-based recommendation text."""
        
        if mismatch_type == "extra_csv":
            if action == SuggestedAction.ADD_COLUMN:
                return f"The CSV contains '{column}', which is not present in the existing table. This appears to be a potentially valuable column that could enhance the table's data completeness."
            else:
                return f"The CSV contains '{column}', which does not have a corresponding column in the target table. This column can be safely ignored for this append operation."
        elif mismatch_type == "missing":
            return f"The table column '{column}' is not present in the CSV upload. The system will use default values or NULL for this column during the append operation."
        elif mismatch_type == "type_mismatch":
            if action == SuggestedAction.TRANSFORM:
                return f"The CSV column '{column}' has a different data type than the corresponding table column. Data type transformation will be required to ensure compatibility."
            else:
                return f"The CSV column '{column}' has incompatible data types with the table schema. This requires careful review to prevent data corruption."
        else:
            return f"Column '{column}' requires attention due to structural differences between the CSV and target table."
    
    def _generate_cache_key(
        self,
        csv_columns: List[str],
        table_columns: Dict[str, str],
        table_name: str,
        extra_csv_columns: List[str],
        missing_table_columns: List[str]
    ) -> str:
        """Generate cache key for recommendations."""
        
        key_data = {
            'table': table_name,
            'csv_cols': sorted(csv_columns),
            'table_cols': sorted(table_columns.keys()),
            'extra_csv': sorted(extra_csv_columns),
            'missing_table': sorted(missing_table_columns)
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        import hashlib
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[ColumnMismatchRecommendation]]:
        """Get recommendations from cache if not expired."""
        with self._cache_lock:
            entry = self._recommendation_cache.get(cache_key)
            if entry and time.time() - entry['timestamp'] < self._cache_ttl:
                return entry['recommendations']
            elif entry:
                # Remove expired entry
                del self._recommendation_cache[cache_key]
            return None
    
    def _set_cache(self, cache_key: str, recommendations: List[ColumnMismatchRecommendation]) -> None:
        """Set recommendations in cache."""
        with self._cache_lock:
            self._recommendation_cache[cache_key] = {
                'recommendations': recommendations,
                'timestamp': time.time()
            }

    def _is_ai_circuit_closed(self) -> bool:
        """Check if AI circuit breaker is closed (AI calls allowed)."""
        current_time = time.time()
        if current_time > self._ai_circuit_open_until:
            # Circuit timeout expired, reset
            self._ai_failure_count = 0
            self._ai_circuit_open_until = 0
            return True
        return self._ai_circuit_open_until == 0

    def _record_ai_failure(self) -> None:
        """Record an AI service failure and potentially open circuit."""
        self._ai_failure_count += 1
        if self._ai_failure_count >= self._ai_failure_threshold:
            self._ai_circuit_open_until = time.time() + self._ai_circuit_timeout
            logger.warning(f"AI circuit breaker opened after {self._ai_failure_count} failures. "
                         f"Will retry in {self._ai_circuit_timeout} seconds.")

    def _reset_ai_circuit(self) -> None:
        """Reset AI circuit breaker on successful call."""
        if self._ai_failure_count > 0:
            logger.info("AI service recovered, resetting circuit breaker")
            self._ai_failure_count = 0
            self._ai_circuit_open_until = 0
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status for monitoring."""
        current_time = time.time()
        is_open = current_time <= self._ai_circuit_open_until
        time_until_retry = max(0, self._ai_circuit_open_until - current_time) if is_open else 0

        return {
            "circuit_open": is_open,
            "failure_count": self._ai_failure_count,
            "failure_threshold": self._ai_failure_threshold,
            "time_until_retry_seconds": time_until_retry,
            "cache_size": len(self._recommendation_cache),
            "ai_available": self._ai_service.is_any_ai_available(),
            "ai_capabilities": self._ai_service.get_ai_capabilities()
        }

    def clear_cache(self) -> int:
        """Clear all cached recommendations."""
        with self._cache_lock:
            count = len(self._recommendation_cache)
            self._recommendation_cache.clear()
            logger.info(f"Cleared {count} cached recommendation entries")
            return count


def create_llm_column_advisor(
    openai_api_key: Optional[str] = None,
    ai_service: Optional[AIServiceManager] = None
) -> LLMColumnAdvisor:
    """
    Factory function to create an LLM column advisor with optional AI credentials.

    This function provides a convenient way to create a column advisor
    without requiring any specific AI credentials to be available.

    Args:
        openai_api_key: Optional OpenAI API key
        ai_service: Optional pre-configured AI service manager

    Returns:
        Configured LLMColumnAdvisor instance
    """
    return LLMColumnAdvisor(
        openai_api_key=openai_api_key,
        ai_service=ai_service
    )