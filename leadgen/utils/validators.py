"""
Cross-feature validators for the lead generation service.

This module contains validation functions that are used across multiple
features and components of the lead generation system.
"""

import re
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse

from .exceptions import ValidationError, LeadGenSafetyError
# from config.constants import LEADGEN_TABLES, PROTECTED_TABLES

# Define table constants locally since they're not in constants.py
LEADGEN_TABLES = ["leads", "lead_personnel", "scraping_sessions", "lead_analytics"]
PROTECTED_TABLES = ["users", "auth_sessions", "system_config"]


def validate_email(email: str, required: bool = False) -> Optional[str]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        required: Whether email is required
        
    Returns:
        Cleaned email address or None if invalid
        
    Raises:
        ValidationError: If email is required but invalid/missing
    """
    if not email:
        if required:
            raise ValidationError("Email address is required", field="email")
        return None
    
    email = email.strip().lower()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        if required:
            raise ValidationError(f"Invalid email format: {email}", field="email", value=email)
        return None
    
    return email


def validate_phone(phone: str, required: bool = False) -> Optional[str]:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        required: Whether phone is required
        
    Returns:
        Cleaned phone number or None if invalid
        
    Raises:
        ValidationError: If phone is required but invalid/missing
    """
    if not phone:
        if required:
            raise ValidationError("Phone number is required", field="phone")
        return None
    
    # Remove all non-digit characters for validation
    digits = re.sub(r'\D', '', phone)
    
    # Must have at least 10 digits
    if len(digits) < 10:
        if required:
            raise ValidationError(f"Phone number must have at least 10 digits: {phone}", field="phone", value=phone)
        return None
    
    # Format based on length
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        # International or other format
        return phone
    
    
def validate_website(website: str, required: bool = False) -> Optional[str]:
    """
    Validate website URL format.
    
    Args:
        website: Website URL to validate
        required: Whether website is required
        
    Returns:
        Cleaned website URL or None if invalid
        
    Raises:
        ValidationError: If website is required but invalid/missing
    """
    if not website:
        if required:
            raise ValidationError("Website URL is required", field="website")
        return None
    
    website = website.strip().lower()
    
    # Add protocol if missing
    if not website.startswith(('http://', 'https://')):
        website = f"https://{website}"
    
    try:
        parsed = urlparse(website)
        if not parsed.netloc:
            if required:
                raise ValidationError(f"Invalid website URL: {website}", field="website", value=website)
            return None
        
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    except Exception:
        if required:
            raise ValidationError(f"Invalid website URL: {website}", field="website", value=website)
        return None


def validate_company_name(company: str, required: bool = True) -> str:
    """
    Validate company name.
    
    Args:
        company: Company name to validate
        required: Whether company name is required
        
    Returns:
        Cleaned company name
        
    Raises:
        ValidationError: If company name is invalid/missing
    """
    if not company or not company.strip():
        if required:
            raise ValidationError("Company name is required", field="company")
        return ""
    
    company = company.strip()
    
    # Check minimum length
    if len(company) < 2:
        raise ValidationError("Company name must be at least 2 characters long", field="company", value=company)
    
    # Check maximum length
    if len(company) > 255:
        raise ValidationError("Company name cannot exceed 255 characters", field="company", value=company)
    
    return company


def validate_industry(industry: str, allowed_industries: Optional[List[str]] = None) -> Optional[str]:
    """
    Validate industry classification.
    
    Args:
        industry: Industry to validate
        allowed_industries: List of allowed industries (optional)
        
    Returns:
        Validated industry or None
        
    Raises:
        ValidationError: If industry is not in allowed list
    """
    if not industry:
        return None
    
    industry = industry.strip()
    
    if allowed_industries and industry.lower() not in [i.lower() for i in allowed_industries]:
        raise ValidationError(
            f"Industry '{industry}' is not in allowed list: {allowed_industries}",
            field="industry",
            value=industry
        )
    
    return industry


def validate_lead_status(status: str, allowed_statuses: List[str]) -> str:
    """
    Validate lead status.
    
    Args:
        status: Status to validate
        allowed_statuses: List of allowed status values
        
    Returns:
        Validated status
        
    Raises:
        ValidationError: If status is invalid
    """
    if not status:
        raise ValidationError("Lead status is required", field="status")
    
    if status not in allowed_statuses:
        raise ValidationError(
            f"Invalid lead status '{status}'. Allowed values: {allowed_statuses}",
            field="status",
            value=status
        )
    
    return status


def validate_pagination_params(page: int, page_size: int, max_page_size: int = 1000) -> Tuple[int, int]:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number
        page_size: Number of items per page
        max_page_size: Maximum allowed page size
        
    Returns:
        Validated (page, page_size) tuple
        
    Raises:
        ValidationError: If parameters are invalid
    """
    if page < 1:
        raise ValidationError("Page number must be at least 1", field="page", value=page)
    
    if page_size < 1:
        raise ValidationError("Page size must be at least 1", field="page_size", value=page_size)
    
    if page_size > max_page_size:
        raise ValidationError(
            f"Page size cannot exceed {max_page_size}",
            field="page_size",
            value=page_size
        )
    
    return page, page_size


def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate date range parameters.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Validated (start_date, end_date) tuple
        
    Raises:
        ValidationError: If date range is invalid
    """
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(
                "Start date cannot be after end date",
                field="date_range",
                value={"start_date": start_date, "end_date": end_date}
            )
        
        # Check if range is reasonable (not more than 10 years)
        if (end_date - start_date).days > 3650:
            raise ValidationError(
                "Date range cannot exceed 10 years",
                field="date_range"
            )
    
    return start_date, end_date


def validate_search_query(query: str, min_length: int = 2, max_length: int = 500) -> str:
    """
    Validate search query parameters.
    
    Args:
        query: Search query string
        min_length: Minimum query length
        max_length: Maximum query length
        
    Returns:
        Validated query
        
    Raises:
        ValidationError: If query is invalid
    """
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty", field="query")
    
    query = query.strip()
    
    if len(query) < min_length:
        raise ValidationError(
            f"Search query must be at least {min_length} characters long",
            field="query",
            value=query
        )
    
    if len(query) > max_length:
        raise ValidationError(
            f"Search query cannot exceed {max_length} characters",
            field="query",
            value=query
        )
    
    # Check for potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', ';']
    if any(char in query for char in dangerous_chars):
        raise ValidationError(
            "Search query contains invalid characters",
            field="query",
            value=query
        )
    
    return query


def validate_sort_params(sort_by: Optional[str], sort_order: Optional[str], allowed_fields: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate sorting parameters.
    
    Args:
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        allowed_fields: List of allowed sort fields
        
    Returns:
        Validated (sort_by, sort_order) tuple
        
    Raises:
        ValidationError: If sort parameters are invalid
    """
    if sort_by and sort_by not in allowed_fields:
        raise ValidationError(
            f"Invalid sort field '{sort_by}'. Allowed fields: {allowed_fields}",
            field="sort_by",
            value=sort_by
        )
    
    if sort_order and sort_order.lower() not in ['asc', 'desc']:
        raise ValidationError(
            "Sort order must be 'asc' or 'desc'",
            field="sort_order",
            value=sort_order
        )
    
    return sort_by, sort_order.lower() if sort_order else None


def validate_bulk_operation_limit(count: int, max_items: int = 1000) -> int:
    """
    Validate bulk operation item count.
    
    Args:
        count: Number of items to process
        max_items: Maximum allowed items
        
    Returns:
        Validated count
        
    Raises:
        ValidationError: If count exceeds limit
    """
    if count <= 0:
        raise ValidationError("Item count must be greater than 0", field="count", value=count)
    
    if count > max_items:
        raise ValidationError(
            f"Cannot process more than {max_items} items at once",
            field="count",
            value=count
        )
    
    return count


def validate_table_operation(table_name: str, operation: str = "operation") -> None:
    """
    Validate that a table operation is safe for lead generation system.
    
    Args:
        table_name: Name of the table to operate on
        operation: Description of the operation (for error messages)
        
    Raises:
        LeadGenSafetyError: If the operation would affect protected tables
    """
    if table_name in PROTECTED_TABLES:
        raise LeadGenSafetyError(
            f"Safety check failed: {operation} on table '{table_name}' is not allowed. "
            f"This table belongs to other systems and must not be modified by lead generation.",
            table_name=table_name
        )
    
    if table_name not in LEADGEN_TABLES:
        raise ValidationError(
            f"Table '{table_name}' is not a recognized lead generation table. "
            f"Known lead gen tables: {', '.join(LEADGEN_TABLES)}",
            field="table_name",
            value=table_name
        )


def validate_json_field(data: Any, field_name: str, required_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Validate JSON field data.
    
    Args:
        data: Data to validate
        field_name: Name of the field (for error messages)
        required_keys: List of required keys in the JSON object
        
    Returns:
        Validated JSON data
        
    Raises:
        ValidationError: If JSON data is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError(
            f"Field '{field_name}' must be a JSON object",
            field=field_name,
            value=data
        )
    
    if required_keys:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValidationError(
                f"Field '{field_name}' is missing required keys: {missing_keys}",
                field=field_name,
                value=data
            )
    
    return data


def validate_id_format(id_value: str, field_name: str = "id") -> str:
    """
    Validate ID format (UUID or similar).
    
    Args:
        id_value: ID value to validate
        field_name: Name of the ID field
        
    Returns:
        Validated ID
        
    Raises:
        ValidationError: If ID format is invalid
    """
    if not id_value or not id_value.strip():
        raise ValidationError(f"{field_name} is required", field=field_name)
    
    id_value = id_value.strip()
    
    # Check for basic format (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', id_value):
        raise ValidationError(
            f"Invalid {field_name} format. Only alphanumeric characters, hyphens, and underscores are allowed",
            field=field_name,
            value=id_value
        )
    
    # Check length constraints
    if len(id_value) < 1 or len(id_value) > 255:
        raise ValidationError(
            f"{field_name} must be between 1 and 255 characters long",
            field=field_name,
            value=id_value
        )
    
    return id_value


def validate_lead_create_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate lead creation data.
    
    Args:
        data: Lead data to validate
        
    Returns:
        Validated and cleaned data
        
    Raises:
        ValidationError: If data is invalid
    """
    validated = {}
    
    # Required fields
    validated['company'] = validate_company_name(data.get('company'), required=True)
    
    # Optional contact information
    if 'email' in data:
        validated['email'] = validate_email(data['email'])
    
    if 'phone' in data:
        validated['phone'] = validate_phone(data['phone'])
    
    if 'website' in data:
        validated['website'] = validate_website(data['website'])
    
    # Optional fields with basic validation
    if 'industry' in data and data['industry']:
        validated['industry'] = data['industry'].strip()
    
    if 'location' in data and data['location']:
        validated['location'] = data['location'].strip()
    
    if 'description' in data and data['description']:
        validated['description'] = data['description'].strip()
    
    return validated


def validate_personnel_create_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate personnel creation data.
    
    Args:
        data: Personnel data to validate
        
    Returns:
        Validated and cleaned data
        
    Raises:
        ValidationError: If data is invalid
    """
    validated = {}
    
    # Required fields
    validated['full_name'] = data.get('full_name', '').strip()
    if not validated['full_name']:
        raise ValidationError("Full name is required", field="full_name")
    
    # Split name into parts
    name_parts = validated['full_name'].split()
    validated['first_name'] = name_parts[0] if name_parts else ''
    validated['last_name'] = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    
    # Optional contact information
    if 'email' in data:
        validated['email'] = validate_email(data['email'])
    
    if 'phone' in data:
        validated['phone'] = validate_phone(data['phone'])
    
    # Optional fields
    if 'position' in data and data['position']:
        validated['position'] = data['position'].strip()
    
    return validated