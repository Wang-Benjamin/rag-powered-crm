"""Template placeholder utilities for mass email.

Shared across CRM and Leadgen. Supports both {placeholder} and [placeholder] syntax.
"""

import re
import logging
from typing import Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_PLACEHOLDER_PATTERN = re.compile(r'[\{\[](\w+)[\}\]]')


def extract_placeholders(template: str) -> List[str]:
    """Extract all unique placeholder names from a template.

    Supports both {placeholder} and [placeholder] syntax.
    """
    return list(set(_PLACEHOLDER_PATTERN.findall(template)))


def validate_placeholders(
    placeholders: List[str],
    valid_set: Optional[Set[str]] = None,
) -> Tuple[bool, List[str]]:
    """Validate placeholder names.

    Args:
        placeholders: List of placeholder names to validate.
        valid_set: Optional whitelist. If None, all placeholders are accepted
                   (CRM flexible mode). If provided, only names in the set
                   are valid (Leadgen whitelist mode).

    Returns:
        (is_valid, invalid_placeholders)
    """
    if valid_set is None:
        return (True, [])

    invalid = [p for p in placeholders if p not in valid_set]
    if invalid:
        logger.warning(f"Invalid placeholders found: {invalid}")
    return (len(invalid) == 0, invalid)


def render_template(template: str, data: Any) -> str:
    """Replace {placeholders} and [placeholders] with actual data.

    Args:
        template: Template string with placeholder tokens.
        data: Dict or object with attributes matching placeholder names.
              Missing keys and None/whitespace values become empty string.
    """
    placeholders = extract_placeholders(template)

    result = template
    for placeholder in placeholders:
        if isinstance(data, dict):
            value = data.get(placeholder)
        else:
            value = getattr(data, placeholder, None)

        if value is None or (isinstance(value, str) and not value.strip()):
            value = ""

        result = result.replace(f"{{{placeholder}}}", str(value))
        result = result.replace(f"[{placeholder}]", str(value))

    return result


def check_missing_data(items: List[Any], placeholders: List[str]) -> List[dict]:
    """Report which items are missing data for required placeholders.

    Args:
        items: List of dicts or objects (leads, clients, etc.).
        placeholders: Placeholder names to check.

    Returns:
        List of warning dicts: {item_id, name, missing_fields}.
        Empty list if all items have complete data.
    """
    warnings = []

    for item in items:
        missing = []
        for placeholder in placeholders:
            if isinstance(item, dict):
                value = item.get(placeholder)
            else:
                value = getattr(item, placeholder, None)

            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(placeholder)

        if missing:
            if isinstance(item, dict):
                item_id = str(item.get('lead_id') or item.get('client_id') or 'unknown')
                name = item.get('company') or item.get('name')
            else:
                item_id = str(getattr(item, 'lead_id', None) or getattr(item, 'client_id', 'unknown'))
                name = getattr(item, 'company', None) or getattr(item, 'name', None)

            warnings.append({
                'item_id': item_id,
                'name': name,
                'missing_fields': missing,
            })

    return warnings
