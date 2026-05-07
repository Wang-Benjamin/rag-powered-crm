"""
Confidence scoring utility for column mappings.
Calculates mapping confidence based on various factors.

CONFIDENCE SCALE: All confidence values use 0-100 scale
- 90+ (HIGH): Auto-mapping threshold for quick upload
- 70+ (MEDIUM): Review needed threshold  
- 50+ (LOW): Minimum apply threshold
- <50: Requires manual intervention
"""

import logging
from typing import List, Dict, Any
from ..models.mapping_models import MappingRule, MappingType
from .confidence_constants import ConfidenceThresholds, ActionThresholds, get_suggested_action

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Calculate confidence scores for column mappings."""
    
    @staticmethod
    def calculate_overall_confidence(mapping_rules: List[MappingRule], target_schema: List[str]) -> float:
        """
        Calculate overall confidence for a set of mapping rules.
        
        Args:
            mapping_rules: List of mapping rules with individual confidence scores
            target_schema: List of target column names
            
        Returns:
            Overall confidence score (0-100)
        """
        if not target_schema:
            return 0.0
            
        if not mapping_rules:
            return 0.0
        
        # Count successfully mapped columns
        mapped_targets = set()
        total_confidence = 0.0
        mapped_count = 0
        
        for rule in mapping_rules:
            if rule.target_column:
                mapped_targets.add(rule.target_column)
                total_confidence += rule.confidence
                mapped_count += 1
        
        # Calculate coverage (percentage of target columns mapped)
        coverage_score = len(mapped_targets) / len(target_schema)
        
        # Calculate average confidence of mapped columns
        avg_confidence = total_confidence / mapped_count if mapped_count > 0 else 0
        
        # Weighted combination: 60% coverage, 40% average confidence
        overall_score = (coverage_score * 60) + (avg_confidence * 0.4)
        
        return min(100.0, max(0.0, overall_score))
    
    @staticmethod
    def calculate_mapping_confidence(
        source_column: str, 
        target_column: str, 
        mapping_type: MappingType,
        reasoning: str = "",
        additional_context: Dict[str, Any] = None
    ) -> float:
        """
        Calculate confidence score for a single mapping.
        
        Args:
            source_column: Source column name
            target_column: Target column name  
            mapping_type: Type of mapping used
            reasoning: AI reasoning for the mapping
            additional_context: Additional context for scoring
            
        Returns:
            Confidence score (0-100)
        """
        base_confidence = ConfidenceScorer._get_base_confidence_by_type(mapping_type)
        
        # Adjust based on name similarity
        name_similarity = ConfidenceScorer._calculate_name_similarity(source_column, target_column)
        name_bonus = name_similarity * 10  # Up to 10 point bonus
        
        # Adjust based on reasoning quality (for AI mappings)
        reasoning_bonus = 0
        if mapping_type == MappingType.AI and reasoning:
            reasoning_bonus = ConfidenceScorer._score_reasoning_quality(reasoning)
        
        # Apply context-specific adjustments
        context_adjustment = 0
        if additional_context:
            context_adjustment = ConfidenceScorer._calculate_context_adjustment(
                source_column, target_column, additional_context
            )
        
        # Calculate final confidence
        final_confidence = base_confidence + name_bonus + reasoning_bonus + context_adjustment
        
        return min(100.0, max(0.0, final_confidence))
    
    @staticmethod
    def _get_base_confidence_by_type(mapping_type: MappingType) -> float:
        """Get base confidence score by mapping type."""
        type_confidence = {
            MappingType.EXACT: 95.0,      # Exact matches are very confident
            MappingType.PATTERN: 75.0,    # Pattern matches are good
            MappingType.SEMANTIC: 70.0,   # AI semantic matches are decent
            MappingType.AI: 65.0,         # General AI matches need review
            MappingType.MANUAL: 100.0     # Manual mappings are definitive
        }
        return type_confidence.get(mapping_type, 50.0)
    
    @staticmethod
    def _calculate_name_similarity(source: str, target: str) -> float:
        """
        Calculate similarity between column names (0-1 scale).
        Uses various similarity metrics.
        """
        if not source or not target:
            return 0.0
        
        source_clean = ConfidenceScorer._clean_column_name(source)
        target_clean = ConfidenceScorer._clean_column_name(target)
        
        # Exact match
        if source_clean == target_clean:
            return 1.0
        
        # Substring match
        if source_clean in target_clean or target_clean in source_clean:
            return 0.8
        
        # Word overlap
        source_words = set(source_clean.split('_'))
        target_words = set(target_clean.split('_'))
        
        if source_words and target_words:
            overlap = len(source_words.intersection(target_words))
            union = len(source_words.union(target_words))
            jaccard_similarity = overlap / union if union > 0 else 0
            
            if jaccard_similarity > 0:
                return jaccard_similarity
        
        # Levenshtein-like distance (simple version)
        return ConfidenceScorer._simple_string_similarity(source_clean, target_clean)
    
    @staticmethod
    def _clean_column_name(name: str) -> str:
        """Clean and normalize column name for comparison."""
        import re
        # Convert to lowercase
        clean = name.lower()
        # Replace common separators with underscores
        clean = re.sub(r'[^\w]', '_', clean)
        # Remove multiple underscores
        clean = re.sub(r'_+', '_', clean)
        # Remove leading/trailing underscores
        clean = clean.strip('_')
        return clean
    
    @staticmethod
    def _simple_string_similarity(s1: str, s2: str) -> float:
        """Calculate simple string similarity (0-1 scale)."""
        if not s1 or not s2:
            return 0.0
        
        if s1 == s2:
            return 1.0
        
        # Simple character-based similarity
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        
        # Count matching characters in order
        matches = 0
        min_len = min(len(s1), len(s2))
        
        for i in range(min_len):
            if s1[i] == s2[i]:
                matches += 1
            else:
                break
        
        return matches / max_len
    
    @staticmethod
    def _score_reasoning_quality(reasoning: str) -> float:
        """Score the quality of AI reasoning (0-10 scale)."""
        if not reasoning:
            return 0.0
        
        score = 0.0
        reasoning_lower = reasoning.lower()
        
        # Positive indicators
        positive_indicators = [
            'semantically equivalent', 'same meaning', 'similar concept',
            'represents the same', 'both refer to', 'exact match',
            'clear correspondence', 'obvious mapping', 'direct relationship'
        ]
        
        for indicator in positive_indicators:
            if indicator in reasoning_lower:
                score += 2.0
                break
        
        # Explanation quality
        if len(reasoning.split()) >= 5:  # At least 5 words
            score += 1.0
        
        if any(word in reasoning_lower for word in ['because', 'since', 'as', 'due to']):
            score += 1.0  # Has causal reasoning
        
        # Uncertainty indicators (reduce confidence)
        uncertainty_indicators = [
            'might be', 'could be', 'possibly', 'uncertain',
            'not sure', 'maybe', 'perhaps', 'likely'
        ]
        
        for indicator in uncertainty_indicators:
            if indicator in reasoning_lower:
                score -= 1.0
        
        return min(10.0, max(0.0, score))
    
    @staticmethod
    def _calculate_context_adjustment(
        source: str, 
        target: str, 
        context: Dict[str, Any]
    ) -> float:
        """Calculate confidence adjustment based on additional context."""
        adjustment = 0.0
        
        # Service context adjustment
        service_type = context.get('service_type', '')
        if service_type == 'sales':
            # Boost confidence for known sales-related mappings
            sales_patterns = {
                ('sales_amount', 'total_sales'): 5.0,
                ('revenue', 'total_sales'): 5.0,
                ('employee_name', 'salesrep_name'): 5.0,
                ('rep_name', 'employee_name'): 5.0,
                ('location', 'province_state'): 3.0,
                ('state', 'location'): 3.0
            }
            
            source_clean = ConfidenceScorer._clean_column_name(source)
            target_clean = ConfidenceScorer._clean_column_name(target)
            
            for (s_pattern, t_pattern), bonus in sales_patterns.items():
                if (s_pattern in source_clean and t_pattern in target_clean) or \
                   (t_pattern in source_clean and s_pattern in target_clean):
                    adjustment += bonus
                    break
        
        # Data quality adjustment
        source_quality = context.get('source_data_quality', {}).get(source, {})
        if source_quality:
            null_percentage = source_quality.get('null_percentage', 0)
            if null_percentage > 50:  # High null percentage reduces confidence
                adjustment -= 5.0
            elif null_percentage < 10:  # Low null percentage increases confidence
                adjustment += 2.0
        
        return adjustment
    
    @staticmethod
    def get_suggested_action(confidence: float, mapping_type: MappingType) -> str:
        """Get suggested action based on confidence score (0-100 scale)."""
        return get_suggested_action(confidence)
    
    @staticmethod
    def calculate_data_quality_score(issues: List[Dict[str, Any]]) -> float:
        """
        Calculate overall data quality score based on issues found.
        
        Args:
            issues: List of data quality issues
            
        Returns:
            Data quality score (0-100, higher is better)
        """
        if not issues:
            return 100.0
        
        total_penalty = 0.0
        
        for issue in issues:
            severity = issue.get('severity', 'low')
            percentage = issue.get('percentage', 0)
            
            # Calculate penalty based on severity and extent
            if severity == 'high':
                penalty = percentage * 0.8  # High severity issues heavily penalized
            elif severity == 'medium':
                penalty = percentage * 0.5  # Medium severity moderately penalized  
            else:
                penalty = percentage * 0.2  # Low severity lightly penalized
            
            total_penalty += penalty
        
        # Cap the penalty at 100 points
        total_penalty = min(100.0, total_penalty)
        
        return max(0.0, 100.0 - total_penalty)