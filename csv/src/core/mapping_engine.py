"""
Enhanced mapping engine with AI-powered pattern recognition.
Refactored as a pure library component suitable for standalone use.
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from ..models.mapping_models import (
    MappingRule, MappingType, SuggestedAction, 
    MappingConfig, TableSchema, ColumnAnalysis
)
from ..utils.confidence_scorer import ConfidenceScorer
from ..utils.confidence_constants import ConfidenceThresholds, ActionThresholds

logger = logging.getLogger(__name__)


class DynamicMappingEngine:
    """Enhanced AI-powered mapping engine with contextual understanding.
    
    This engine is designed to work as a standalone library component without
    web framework dependencies. AI services are optional and can be injected.
    """
    
    def __init__(self, 
                 config: MappingConfig = None,
                 ai_service: Optional[Any] = None,
                 enable_cache: bool = True):
        self.config = config or MappingConfig()
        self.ai_service = ai_service
        self.confidence_scorer = ConfidenceScorer()
        self.enable_cache = enable_cache
        
        # Cache for mapping results
        self._mapping_cache: Dict[str, List[MappingRule]] = {} if enable_cache else None
        
        # Optional AI service loader function
        self._ai_service_loader: Optional[Callable[[], Any]] = None
    
    def set_ai_service_loader(self, loader_func: Callable[[], Any]) -> None:
        """Set a function to load AI service on demand.
        
        Args:
            loader_func: Function that returns an AI service instance when called
        """
        self._ai_service_loader = loader_func
    
    def _get_ai_service(self) -> Optional[Any]:
        """Get AI service instance, loading it on demand if needed."""
        if self.ai_service is None and self._ai_service_loader is not None:
            try:
                self.ai_service = self._ai_service_loader()
                logger.info("AI service loaded on demand")
            except Exception as e:
                logger.warning(f"Failed to load AI service: {e}")
        return self.ai_service
    
    def _is_ai_available(self) -> bool:
        """Check if AI service is available."""
        ai_service = self._get_ai_service()
        if ai_service is None:
            return False
        
        # Check if the AI service has the required methods
        return (hasattr(ai_service, 'is_any_ai_available') and 
                callable(getattr(ai_service, 'is_any_ai_available')) and
                ai_service.is_any_ai_available())
    
    async def analyze_columns(
        self, 
        source_columns: List[ColumnAnalysis], 
        target_schema: Optional[TableSchema],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> List[MappingRule]:
        """
        Analyze columns using hybrid approach (deterministic + AI + semantic).
        
        Args:
            source_columns: List of analyzed source columns
            target_schema: Target table schema (if exists)
            additional_context: Additional context for mapping
            
        Returns:
            List of MappingRule objects with confidence scores
        """
        if not target_schema or not target_schema.columns:
            logger.warning("No target schema provided, returning empty mappings")
            return []
        
        source_names = [col.name for col in source_columns]
        target_names = [col.name for col in target_schema.columns]
        
        # Check cache first (if enabled)
        cache_key = None
        if self._mapping_cache is not None:
            cache_key = f"{hash(tuple(source_names))}:{hash(tuple(target_names))}:{self.config.service_context}"
            if cache_key in self._mapping_cache:
                logger.info("Using cached mapping results")
                return self._mapping_cache[cache_key]
        
        # Step 1: Try deterministic mapping first
        deterministic_mappings = self._deterministic_mapping(source_names, target_names)
        logger.info(f"Deterministic mapping found {len(deterministic_mappings)} mappings")
        
        # Step 2: Calculate success rate and decide on AI usage
        success_rate = self._calculate_mapping_success(deterministic_mappings, target_names)
        logger.info(f"Deterministic mapping success rate: {success_rate:.2f}")
        
        final_mappings = []
        
        if self.config.use_ai_fallback and self._is_ai_available():
            # Use AI for enhanced mapping
            logger.info("Using AI-enhanced mapping")
            try:
                ai_mappings = await self._ai_enhanced_mapping(
                    source_names, target_names, additional_context or {}
                )
                final_mappings = self._create_mapping_rules(
                    ai_mappings, source_columns, MappingType.AI
                )
            except Exception as e:
                logger.error(f"AI mapping failed, falling back to deterministic: {e}")
                final_mappings = self._create_mapping_rules(
                    deterministic_mappings, source_columns, MappingType.PATTERN
                )
        else:
            # Use deterministic mappings when AI not available
            final_mappings = self._create_mapping_rules(
                deterministic_mappings, source_columns, MappingType.PATTERN
            )
            logger.info("Using deterministic mappings (AI not available)")
        
        # Step 3: Apply confidence scoring and additional analysis
        enhanced_mappings = self._enhance_mapping_confidence(
            final_mappings, source_columns, target_schema, additional_context or {}
        )
        
        # Cache the results (if caching is enabled)
        if self._mapping_cache is not None and cache_key is not None:
            self._mapping_cache[cache_key] = enhanced_mappings
        
        logger.info(f"Final mapping analysis: {len(enhanced_mappings)} rules generated")
        return enhanced_mappings
    
    def analyze_columns_sync(
        self, 
        source_columns: List[ColumnAnalysis], 
        target_schema: Optional[TableSchema],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> List[MappingRule]:
        """Synchronous version of analyze_columns.
        
        This method provides the same functionality as analyze_columns but runs
        synchronously, making it suitable for environments where async is not preferred.
        
        Note: AI-enhanced mapping will be disabled in sync mode unless you provide
        a synchronous AI service.
        
        Args:
            source_columns: List of analyzed source columns
            target_schema: Target table schema (if exists)
            additional_context: Additional context for mapping
            
        Returns:
            List of MappingRule objects with confidence scores
        """
        if not target_schema or not target_schema.columns:
            logger.warning("No target schema provided, returning empty mappings")
            return []
        
        source_names = [col.name for col in source_columns]
        target_names = [col.name for col in target_schema.columns]
        
        # Check cache first (if enabled)
        cache_key = None
        if self._mapping_cache is not None:
            cache_key = f"sync_{hash(tuple(source_names))}:{hash(tuple(target_names))}:{self.config.service_context}"
            if cache_key in self._mapping_cache:
                logger.info("Using cached mapping results (sync)")
                return self._mapping_cache[cache_key]
        
        # Step 1: Try deterministic mapping first
        deterministic_mappings = self._deterministic_mapping(source_names, target_names)
        logger.info(f"Deterministic mapping found {len(deterministic_mappings)} mappings")
        
        # Step 2: Calculate success rate
        success_rate = self._calculate_mapping_success(deterministic_mappings, target_names)
        logger.info(f"Deterministic mapping success rate: {success_rate:.2f}")
        
        # For sync mode, we use deterministic mappings only
        # AI services typically require async operations
        final_mappings = self._create_mapping_rules(
            deterministic_mappings, source_columns, MappingType.PATTERN
        )
        
        if success_rate < self.config.confidence_threshold:
            logger.info("Low confidence in sync mode - consider using async version with AI")
        
        # Step 3: Apply confidence scoring and additional analysis
        enhanced_mappings = self._enhance_mapping_confidence(
            final_mappings, source_columns, target_schema, additional_context or {}
        )
        
        # Cache the results (if caching is enabled)
        if self._mapping_cache is not None and cache_key is not None:
            self._mapping_cache[cache_key] = enhanced_mappings
        
        logger.info(f"Final mapping analysis (sync): {len(enhanced_mappings)} rules generated")
        return enhanced_mappings
    
    def _deterministic_mapping(self, source_columns: List[str], target_schema: List[str]) -> Dict[str, str]:
        """Enhanced deterministic column mapping with domain-specific patterns."""
        mapping = {}
        
        # Get domain-specific patterns
        patterns = self._get_domain_patterns()
        
        # Step 1: Try exact matches first (highest confidence)
        for target_col in target_schema:
            for source_col in source_columns:
                if source_col.lower() == target_col.lower():
                    mapping[source_col] = target_col
                    break
        
        # Step 2: Try pattern-based matching for unmapped columns
        unmapped_sources = [col for col in source_columns if col not in mapping]
        unmapped_targets = [col for col in target_schema if col not in mapping.values()]
        
        for target_col in unmapped_targets:
            target_lower = target_col.lower()
            
            # Check if we have patterns for this target column
            if target_lower in patterns:
                target_patterns = patterns[target_lower]
                
                for source_col in unmapped_sources:
                    source_lower = source_col.lower()
                    
                    # Direct pattern match
                    if source_lower in target_patterns:
                        mapping[source_col] = target_col
                        break
                    
                    # Substring pattern match
                    if any(pattern in source_lower for pattern in target_patterns):
                        mapping[source_col] = target_col
                        break
                    
                    # Reverse pattern match (source pattern in target)
                    if any(source_word in target_patterns for source_word in source_lower.split('_')):
                        mapping[source_col] = target_col
                        break
        
        # Step 3: Try fuzzy matching for remaining columns
        remaining_sources = [col for col in source_columns if col not in mapping]
        remaining_targets = [col for col in target_schema if col not in mapping.values()]
        
        for source_col in remaining_sources:
            best_target = None
            best_similarity = 0.0
            
            for target_col in remaining_targets:
                similarity = self._calculate_name_similarity(source_col, target_col)
                if similarity > best_similarity and similarity > 0.6:  # Minimum similarity threshold
                    best_similarity = similarity
                    best_target = target_col
            
            if best_target:
                mapping[source_col] = best_target
                remaining_targets.remove(best_target)
        
        return mapping
    
    def _get_domain_patterns(self) -> Dict[str, List[str]]:
        """Get domain-specific mapping patterns based on service context.
        
        NOTE: Hardcoded patterns have been removed to rely on AI semantic matching.
        This prevents problematic pattern matches like 'Customer Code' -> 'id'.
        Only exact matching will be used for deterministic mapping.
        """
        # Return empty patterns dictionary to disable pattern-based matching
        # This forces the system to rely on exact matching + AI semantic analysis
        return {}
    
    async def _ai_enhanced_mapping(
        self, 
        source_columns: List[str], 
        target_schema: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Use AI for intelligent column mapping with context."""
        ai_service = self._get_ai_service()
        if ai_service is None:
            logger.warning("No AI service available for enhanced mapping")
            return {}
        
        try:
            # Call AI service for analysis
            ai_response = await ai_service.analyze_column_mappings(
                source_columns, target_schema, self.config.service_context
            )
            
            # Convert AI response to mapping dictionary
            mapping = {}
            for ai_mapping in ai_response.get('mappings', []):
                source_col = ai_mapping.get('source_column')
                target_col = ai_mapping.get('target_column')
                confidence = ai_mapping.get('confidence', 0)
                
                # Only accept mappings with sufficient confidence (minimum apply threshold)
                if source_col and target_col and confidence >= ConfidenceThresholds.APPLY:
                    mapping[source_col] = target_col
            
            logger.info(f"AI mapping generated {len(mapping)} mappings")
            return mapping
            
        except Exception as e:
            logger.error(f"AI enhanced mapping failed: {e}")
            return {}
    
    def _create_mapping_rules(
        self, 
        mappings: Dict[str, str], 
        source_columns: List[ColumnAnalysis],
        mapping_type: MappingType
    ) -> List[MappingRule]:
        """Create MappingRule objects from mapping dictionary."""
        rules = []
        
        # Create mapping rules for mapped columns
        for source_name, target_name in mappings.items():
            # Find source column analysis
            source_analysis = next(
                (col for col in source_columns if col.name == source_name), None
            )
            
            if not source_analysis:
                continue
            
            # Calculate confidence based on mapping type and name similarity
            base_confidence = self.confidence_scorer._get_base_confidence_by_type(mapping_type)
            name_similarity = self.confidence_scorer._calculate_name_similarity(source_name, target_name)
            
            # Adjust confidence based on data quality
            quality_adjustment = 0
            if source_analysis.null_percentage > 50:
                quality_adjustment -= 10
            elif source_analysis.null_percentage < 10:
                quality_adjustment += 5
            
            final_confidence = min(100.0, max(0.0, base_confidence + (name_similarity * 10) + quality_adjustment))
            
            # Determine suggested action based on standardized thresholds (0-100 scale)
            suggested_action = SuggestedAction.AUTO if final_confidence >= ActionThresholds.AUTO else \
                             SuggestedAction.REVIEW if final_confidence >= ActionThresholds.REVIEW else \
                             SuggestedAction.MANUAL
            
            rule = MappingRule(
                source_column=source_name,
                target_column=target_name,
                confidence=final_confidence,
                mapping_type=mapping_type,
                suggested_action=suggested_action,
                reasoning=f"Mapped using {mapping_type.value} with {final_confidence:.1f}% confidence"
            )
            
            rules.append(rule)
        
        # Create rules for unmapped columns
        mapped_sources = set(mappings.keys())
        for source_col in source_columns:
            if source_col.name not in mapped_sources:
                rule = MappingRule(
                    source_column=source_col.name,
                    target_column=None,
                    confidence=0.0,
                    mapping_type=MappingType.MANUAL,
                    suggested_action=SuggestedAction.MANUAL,
                    reasoning="No suitable target column found"
                )
                rules.append(rule)
        
        return rules
    
    def _enhance_mapping_confidence(
        self,
        mappings: List[MappingRule],
        source_columns: List[ColumnAnalysis],
        target_schema: TableSchema,
        context: Dict[str, Any]
    ) -> List[MappingRule]:
        """Enhance mapping confidence with additional analysis."""
        enhanced_mappings = []
        
        # Build context for confidence scoring
        scoring_context = {
            'service_type': self.config.service_context,
            'source_data_quality': {
                col.name: {
                    'null_percentage': col.null_percentage,
                    'unique_count': col.unique_count,
                    'data_quality_issues': col.data_quality_issues
                }
                for col in source_columns
            }
        }
        scoring_context.update(context)
        
        for mapping in mappings:
            if mapping.target_column:
                # Recalculate confidence with enhanced context
                enhanced_confidence = self.confidence_scorer.calculate_mapping_confidence(
                    mapping.source_column,
                    mapping.target_column,
                    mapping.mapping_type,
                    mapping.reasoning or "",
                    scoring_context
                )
                
                # Update confidence and suggested action
                mapping.confidence = enhanced_confidence
                mapping.suggested_action = SuggestedAction(
                    self.confidence_scorer.get_suggested_action(enhanced_confidence, mapping.mapping_type)
                )
            
            enhanced_mappings.append(mapping)
        
        return enhanced_mappings
    
    def _calculate_mapping_success(self, mapping: Dict[str, str], target_schema: List[str]) -> float:
        """Calculate mapping success rate."""
        if not target_schema:
            return 0.0
        
        mapped_targets = set(mapping.values())
        return len(mapped_targets) / len(target_schema)
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two column names (0-1 scale)."""
        return self.confidence_scorer._calculate_name_similarity(name1, name2)
    
    def get_mapping_statistics(self, mappings: List[MappingRule]) -> Dict[str, Any]:
        """Generate statistics about the mapping results."""
        if not mappings:
            return {
                'total_columns': 0,
                'mapped_columns': 0,
                'unmapped_columns': 0,
                'average_confidence': 0.0,
                'auto_mappings': 0,
                'review_mappings': 0,
                'manual_mappings': 0
            }
        
        mapped_count = sum(1 for m in mappings if m.target_column)
        total_confidence = sum(m.confidence for m in mappings if m.target_column)
        avg_confidence = total_confidence / mapped_count if mapped_count > 0 else 0.0
        
        action_counts = {
            SuggestedAction.AUTO: 0,
            SuggestedAction.REVIEW: 0,
            SuggestedAction.MANUAL: 0
        }
        
        for mapping in mappings:
            action_counts[mapping.suggested_action] = action_counts.get(mapping.suggested_action, 0) + 1
        
        return {
            'total_columns': len(mappings),
            'mapped_columns': mapped_count,
            'unmapped_columns': len(mappings) - mapped_count,
            'average_confidence': avg_confidence,
            'auto_mappings': action_counts[SuggestedAction.AUTO],
            'review_mappings': action_counts[SuggestedAction.REVIEW],
            'manual_mappings': action_counts[SuggestedAction.MANUAL]
        }
    
    def clear_cache(self) -> None:
        """Clear the mapping cache."""
        if self._mapping_cache is not None:
            self._mapping_cache.clear()
            logger.info("Mapping cache cleared")
        else:
            logger.info("Cache not enabled, nothing to clear")
    
    def get_cache_size(self) -> int:
        """Get the current size of the mapping cache."""
        if self._mapping_cache is not None:
            return len(self._mapping_cache)
        return 0
    
    def export_mappings_as_dict(
        self, 
        mappings: List[MappingRule], 
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Export mapping rules as a dictionary for serialization.
        
        Args:
            mappings: List of mapping rules to export
            include_metadata: Whether to include confidence and reasoning
            
        Returns:
            Dictionary representation of mappings
        """
        result = {
            "mappings": [],
            "statistics": self.get_mapping_statistics(mappings)
        }
        
        for mapping in mappings:
            mapping_dict = {
                "source_column": mapping.source_column,
                "target_column": mapping.target_column,
            }
            
            if include_metadata:
                mapping_dict.update({
                    "confidence": mapping.confidence,
                    "mapping_type": mapping.mapping_type.value,
                    "suggested_action": mapping.suggested_action.value,
                    "reasoning": mapping.reasoning
                })
            
            result["mappings"].append(mapping_dict)
        
        return result
    
    def create_simple_mappings(
        self, 
        source_columns: List[str], 
        target_columns: List[str]
    ) -> Dict[str, str]:
        """Create simple deterministic mappings without full analysis.
        
        This is a lightweight method for basic mapping scenarios where you don't
        need the full analysis pipeline.
        
        Args:
            source_columns: List of source column names
            target_columns: List of target column names
            
        Returns:
            Dictionary mapping source to target columns
        """
        return self._deterministic_mapping(source_columns, target_columns)
    
    def validate_mappings(
        self, 
        mappings: List[MappingRule], 
        source_columns: List[str],
        target_columns: List[str]
    ) -> List[str]:
        """Validate mapping rules against available columns.
        
        Args:
            mappings: List of mapping rules to validate
            source_columns: Available source column names
            target_columns: Available target column names
            
        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []
        
        for mapping in mappings:
            if mapping.source_column not in source_columns:
                errors.append(f"Source column '{mapping.source_column}' not found")
            
            if mapping.target_column and mapping.target_column not in target_columns:
                errors.append(f"Target column '{mapping.target_column}' not found")
        
        return errors
    
    def set_config(self, config: MappingConfig) -> None:
        """Update the mapping configuration.
        
        Args:
            config: New mapping configuration
        """
        self.config = config
        logger.info("Mapping configuration updated")