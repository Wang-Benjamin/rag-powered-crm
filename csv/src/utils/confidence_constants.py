"""
Centralized confidence threshold constants for the CSV mapping system.

All confidence values throughout the system use a 0-100 scale for consistency.
These constants ensure uniform behavior across frontend and backend components.
"""

# Standard confidence thresholds (0-100 scale)
class ConfidenceThresholds:
    """Standard confidence thresholds used throughout the system."""
    
    # High confidence - enables auto-mapping and quick upload
    HIGH = 90.0
    
    # Medium confidence - requires review but suggests mapping
    MEDIUM = 70.0
    
    # Low confidence - minimum threshold for applying mappings
    LOW = 50.0
    
    # Apply threshold - minimum confidence to apply a mapping
    APPLY = 50.0


# Action thresholds for mapping suggestions
class ActionThresholds:
    """Thresholds for determining suggested actions."""
    
    AUTO = ConfidenceThresholds.HIGH      # 90+ for automatic mapping
    REVIEW = ConfidenceThresholds.MEDIUM  # 70+ for review needed
    MANUAL = ConfidenceThresholds.LOW     # 50+ minimum, <50 requires manual


# Data quality thresholds (0-100 scale)
class QualityThresholds:
    """Thresholds for data quality assessment."""
    
    EXCELLENT = 95.0
    GOOD = 80.0
    FAIR = 60.0
    POOR = 0.0


def get_confidence_level(score: float) -> str:
    """
    Get confidence level for a score.
    
    Args:
        score: Confidence score (0-100)
        
    Returns:
        Confidence level: 'HIGH', 'MEDIUM', 'LOW', or 'VERY_LOW'
    """
    if score >= ConfidenceThresholds.HIGH:
        return 'HIGH'
    elif score >= ConfidenceThresholds.MEDIUM:
        return 'MEDIUM'
    elif score >= ConfidenceThresholds.LOW:
        return 'LOW'
    else:
        return 'VERY_LOW'


def get_suggested_action(confidence: float) -> str:
    """
    Get suggested action for a confidence score.
    
    Args:
        confidence: Confidence score (0-100)
        
    Returns:
        Suggested action: 'auto', 'review', or 'manual'
    """
    if confidence >= ActionThresholds.AUTO:
        return 'auto'
    elif confidence >= ActionThresholds.REVIEW:
        return 'review'
    else:
        return 'manual'


def validate_confidence_score(score: float) -> bool:
    """
    Validate that a confidence score is within valid range.
    
    Args:
        score: Confidence score to validate
        
    Returns:
        True if score is valid (0-100), False otherwise
    """
    return isinstance(score, (int, float)) and 0 <= score <= 100


def normalize_confidence_score(score: float) -> float:
    """
    Normalize confidence score to 0-100 scale if needed.
    
    Args:
        score: Confidence score to normalize
        
    Returns:
        Normalized score (0-100)
    """
    if score <= 1:
        # Convert from 0-1 scale to 0-100 scale
        return round(score * 100, 2)
    return round(max(0.0, min(100.0, score)), 2)


if __name__ == '__main__':
    # Test script for confidence constants
    print("=== Confidence Constants Test ===")
    print(f"HIGH threshold: {ConfidenceThresholds.HIGH}")
    print(f"MEDIUM threshold: {ConfidenceThresholds.MEDIUM}")
    print(f"LOW threshold: {ConfidenceThresholds.LOW}")
    print(f"APPLY threshold: {ConfidenceThresholds.APPLY}")
    print()
    print(f"AUTO action threshold: {ActionThresholds.AUTO}")
    print(f"REVIEW action threshold: {ActionThresholds.REVIEW}")
    print(f"MANUAL action threshold: {ActionThresholds.MANUAL}")
    print()
    
    # Test confidence levels
    test_scores = [95, 85, 75, 65, 45, 25]
    for score in test_scores:
        level = get_confidence_level(score)
        action = get_suggested_action(score)
        print(f"Score {score}: Level={level}, Action={action}")
    
    print("\n=== All tests passed! ===")