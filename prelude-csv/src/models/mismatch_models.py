"""
Data models for column mismatch analysis and recommendations.

Provides consistent data structures for mismatch analysis across the platform.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class MismatchType(Enum):
    """Types of column mismatches."""
    EXTRA_CSV = "extra_csv"           # Column in CSV but not in table
    EXTRA_TABLE = "extra_table"       # Column in table but not in CSV
    MISSING_TABLE = "missing_table"   # Alias for extra_table (for backward compatibility)
    TYPE_MISMATCH = "type_mismatch"   # Column exists in both but types differ


class Severity(Enum):
    """Severity levels for recommendations."""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"


class SuggestedAction(Enum):
    """Suggested actions for handling mismatches."""
    ADD_COLUMN = "add_column"         # Add new column to table
    IGNORE = "ignore"                 # Ignore the column
    MANUAL_MAP = "manual_map"         # Requires manual mapping
    TRANSFORM = "transform"           # Apply data transformation
    ERROR = "error"                   # Stop processing due to critical issue


@dataclass
class ColumnMismatchRecommendation:
    """Recommendation for handling a specific column mismatch."""
    mismatch_type: MismatchType
    column_name: str
    severity: Severity
    recommendation: str
    suggested_action: SuggestedAction
    confidence: float  # 0.0 to 1.0
    issue_type: str  # "missing", "extra", "different"
    business_context: Optional[str] = None
    technical_details: Optional[str] = None
    source_type: Optional[str] = None
    target_type: Optional[str] = None


@dataclass
class BusinessContext:
    """Business context inferred from table and column analysis."""
    domain: str                    # e.g., "sales", "hr", "inventory"
    table_purpose: str            # e.g., "transaction_data", "employee_records"
    criticality: str              # e.g., "high", "medium", "low"
    business_description: str     # Human readable description
    key_indicators: List[str]     # Column patterns that led to this inference