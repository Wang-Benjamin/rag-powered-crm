"""
Business context inference utilities for CSV mapping.

Provides domain-specific analysis and business rationale generation
for column mismatches and mapping recommendations.
"""

from typing import List, Optional, Tuple
from ..models.mismatch_models import BusinessContext, SuggestedAction


def infer_business_context(
    table_name: str,
    table_columns: List[str],
    csv_columns: List[str],
    schema_name: Optional[str] = None
) -> BusinessContext:
    """
    Infer business context from table and column names.
    
    Args:
        table_name: Name of the target table
        table_columns: List of existing table column names
        csv_columns: List of CSV column names  
        schema_name: Optional schema name for additional context
        
    Returns:
        BusinessContext with inferred domain and metadata
    """
    
    # Domain inference patterns
    domain_patterns = {
        'sales': ['sales', 'revenue', 'order', 'customer', 'invoice', 'product', 'price', 'amount', 'transaction'],
        'hr': ['employee', 'staff', 'payroll', 'salary', 'department', 'manager', 'hire', 'performance'],
        'inventory': ['inventory', 'stock', 'warehouse', 'supplier', 'item', 'quantity', 'sku'],
        'finance': ['account', 'ledger', 'expense', 'budget', 'cost', 'profit', 'financial'],
        'marketing': ['campaign', 'lead', 'conversion', 'click', 'impression', 'engagement'],
        'operations': ['operation', 'process', 'workflow', 'task', 'project', 'milestone']
    }
    
    # Analyze table name and columns
    all_text = f"{table_name} {schema_name or ''} {' '.join(table_columns + csv_columns)}".lower()
    
    # Score each domain
    domain_scores = {}
    key_indicators = []
    
    for domain, keywords in domain_patterns.items():
        score = 0
        found_keywords = []
        for keyword in keywords:
            if keyword in all_text:
                score += 1
                found_keywords.append(keyword)
        
        if score > 0:
            domain_scores[domain] = score
            key_indicators.extend(found_keywords)
    
    # Determine primary domain
    if domain_scores:
        primary_domain = max(domain_scores, key=domain_scores.get)
    else:
        primary_domain = "general"
    
    # Infer table purpose
    purpose_patterns = {
        'transaction_data': ['transaction', 'order', 'sale', 'purchase', 'payment'],
        'master_data': ['customer', 'product', 'employee', 'supplier', 'item'],
        'analytics_data': ['metric', 'kpi', 'performance', 'report', 'dashboard'],
        'operational_data': ['log', 'event', 'status', 'queue', 'process']
    }
    
    table_purpose = "reference_data"  # default
    for purpose, keywords in purpose_patterns.items():
        if any(keyword in all_text for keyword in keywords):
            table_purpose = purpose
            break
    
    # Determine criticality based on domain and purpose
    criticality = "medium"  # default
    if primary_domain in ['sales', 'finance'] and table_purpose == 'transaction_data':
        criticality = "high"
    elif primary_domain in ['hr', 'operations'] and table_purpose == 'master_data':
        criticality = "high"
    elif table_purpose == 'analytics_data':
        criticality = "low"
    
    # Generate business description
    business_description = f"This appears to be a {primary_domain} {table_purpose.replace('_', ' ')} table used for {primary_domain} operations."
    
    return BusinessContext(
        domain=primary_domain,
        table_purpose=table_purpose,
        criticality=criticality,
        business_description=business_description,
        key_indicators=key_indicators[:5]  # Limit to top 5 indicators
    )


def classify_extra_column(
    column: str, 
    business_context: Optional[BusinessContext]
) -> Tuple[str, SuggestedAction, float]:
    """
    Classify extra CSV column using rule-based logic.
    
    Args:
        column: Column name to classify
        business_context: Optional business context for domain-specific rules
        
    Returns:
        Tuple of (severity, suggested_action, confidence)
    """
    
    column_lower = column.lower()
    
    # High-value columns that should typically be added
    high_value_patterns = ['id', 'email', 'phone', 'address', 'name', 'date', 'amount', 'status']
    if any(pattern in column_lower for pattern in high_value_patterns):
        return "medium", SuggestedAction.ADD_COLUMN, 0.8
    
    # System/technical columns that might be less critical
    system_patterns = ['created_at', 'updated_at', 'version', 'hash', 'checksum']
    if any(pattern in column_lower for pattern in system_patterns):
        return "low", SuggestedAction.IGNORE, 0.7
    
    # Business context specific classification
    if business_context:
        if business_context.criticality == "high":
            return "medium", SuggestedAction.ADD_COLUMN, 0.7
        elif business_context.criticality == "low":
            return "low", SuggestedAction.IGNORE, 0.6
    
    # Default classification
    return "medium", SuggestedAction.ADD_COLUMN, 0.6


def classify_missing_column(
    column: str, 
    business_context: Optional[BusinessContext]
) -> Tuple[str, float]:
    """
    Classify missing table column using rule-based logic.
    
    Args:
        column: Column name to classify
        business_context: Optional business context
        
    Returns:
        Tuple of (severity, confidence)
    """
    
    column_lower = column.lower()
    
    # Critical columns that should not be missing
    critical_patterns = ['id', 'primary_key', 'user_id', 'account_id']
    if any(pattern in column_lower for pattern in critical_patterns):
        return "high", 0.9
    
    # Audit columns that can have defaults
    audit_patterns = ['created_at', 'updated_at', 'created_by']
    if any(pattern in column_lower for pattern in audit_patterns):
        return "low", 0.8
    
    return "medium", 0.6


def classify_type_mismatch(
    source_type: str,
    target_type: str,
    business_context: Optional[BusinessContext] = None
) -> Tuple[str, SuggestedAction, float]:
    """
    Classify type mismatch using rule-based logic.
    
    Args:
        source_type: Source data type
        target_type: Target data type
        business_context: Optional business context
        
    Returns:
        Tuple of (severity, suggested_action, confidence)
    """
    
    source_type_lower = source_type.lower()
    target_type_lower = target_type.lower()
    
    # Compatible numeric types
    numeric_types = ['int', 'integer', 'bigint', 'decimal', 'numeric', 'float', 'real']
    if (any(t in source_type_lower for t in numeric_types) and 
        any(t in target_type_lower for t in numeric_types)):
        return "low", SuggestedAction.TRANSFORM, 0.8
    
    # Text types are generally compatible
    text_types = ['text', 'varchar', 'char', 'string']
    if any(t in target_type_lower for t in text_types):
        return "low", SuggestedAction.TRANSFORM, 0.9
    
    # Date/time mismatches need attention
    date_types = ['date', 'timestamp', 'time']
    if (any(t in source_type_lower for t in date_types) or 
        any(t in target_type_lower for t in date_types)):
        return "medium", SuggestedAction.TRANSFORM, 0.7
    
    # Default for incompatible types
    return "high", SuggestedAction.ERROR, 0.6


def get_business_rationale(
    column: str, 
    action: SuggestedAction, 
    business_context: Optional[BusinessContext]
) -> str:
    """
    Generate business rationale for the recommendation.
    
    Args:
        column: Column name
        action: Suggested action
        business_context: Optional business context
        
    Returns:
        Business rationale string
    """
    
    if not business_context:
        return f"Column '{column}' should be handled according to general data management best practices."
    
    domain_context = {
        'sales': f"For {business_context.domain} operations, this column may be valuable for customer analysis and reporting.",
        'hr': f"In {business_context.domain} systems, this column could be important for employee management and compliance.",
        'finance': f"For {business_context.domain} data, this column may be critical for financial reporting and auditing.",
        'inventory': f"In {business_context.domain} management, this column could be essential for tracking and operations.",
        'marketing': f"For {business_context.domain} activities, this column may be valuable for campaign analysis and ROI tracking."
    }
    
    base_context = domain_context.get(
        business_context.domain, 
        f"For {business_context.domain} operations, this column should be evaluated based on business requirements."
    )
    
    if action == SuggestedAction.ADD_COLUMN:
        return f"{base_context} Adding this column would enhance data completeness."
    elif action == SuggestedAction.IGNORE:
        return f"{base_context} This column appears to be non-critical for current operations."
    else:
        return base_context


def get_column_recommendation(
    column_name: str, 
    mismatch_type: str
) -> Tuple[SuggestedAction, str, str]:
    """
    Get specific recommendation for a column based on its name and type.
    
    Args:
        column_name: Name of the column
        mismatch_type: Type of mismatch ("extra" or "missing")
        
    Returns:
        Tuple of (suggested_action, severity, recommendation_text)
    """
    col_lower = column_name.lower()

    # System/metadata columns
    if any(pattern in col_lower for pattern in ['id', 'uuid', 'created_at', 'updated_at', 'version']):
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "low", f"System column '{column_name}' - safe to add to table."
        else:
            return SuggestedAction.IGNORE, "low", f"System column '{column_name}' - likely auto-generated by database."

    # Status/boolean columns
    elif any(pattern in col_lower for pattern in ['status', 'active', 'enabled', 'deleted', 'visible']):
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "low", f"Status column '{column_name}' - useful for data management."
        else:
            return SuggestedAction.TRANSFORM, "medium", f"Status column '{column_name}' - consider setting default value."

    # Contact/personal info columns
    elif any(pattern in col_lower for pattern in ['email', 'phone', 'address', 'name']):
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "medium", f"Contact column '{column_name}' - valuable business data."
        else:
            return SuggestedAction.MANUAL_MAP, "high", f"Contact column '{column_name}' - important data, mapping required."

    # Financial/numeric columns
    elif any(pattern in col_lower for pattern in ['amount', 'price', 'cost', 'total', 'quantity']):
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "medium", f"Financial column '{column_name}' - important business metric."
        else:
            return SuggestedAction.MANUAL_MAP, "high", f"Financial column '{column_name}' - critical data, mapping required."

    # Generic/custom columns
    elif any(pattern in col_lower for pattern in ['col_', 'field_', 'custom_', 'data_']):
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "low", f"Generic column '{column_name}' - likely custom data field."
        else:
            return SuggestedAction.IGNORE, "low", f"Generic column '{column_name}' - likely optional custom field."

    # Default case
    else:
        if mismatch_type == "extra":
            return SuggestedAction.ADD_COLUMN, "low", f"Standard column '{column_name}' - safe to add."
        else:
            return SuggestedAction.IGNORE, "low", f"Column '{column_name}' missing from CSV - likely optional."