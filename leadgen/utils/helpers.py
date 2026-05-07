"""
General helper functions for the lead generation service.

This module contains utility functions that are used across multiple
components of the lead generation system.
"""

import re
import logging
import random
import time
import hashlib
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from urllib.parse import urlparse


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Set up logging configuration for the service."""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean and normalize text data."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove special characters that might cause issues
    text = re.sub(r'[^\w\s\-\.\,\(\)\/\&\@\#\%]', '', text)
    
    return text.strip()


def clean_phone(phone: str) -> str:
    """Clean and standardize phone numbers."""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Format US phone numbers
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    elif len(digits) > 11:
        # International format - keep as is with basic formatting
        return f"+{digits[:len(digits)-10]} ({digits[-10:-7]}) {digits[-7:-4]}-{digits[-4:]}"
    
    return phone


def clean_email(email: str) -> str:
    """Validate and clean email addresses."""
    if not email:
        return ""
    
    email = email.strip().lower()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        return email
    return ""


def clean_website(website: str) -> str:
    """Clean and normalize website URLs."""
    if not website:
        return ""
    
    website = website.strip().lower()
    
    # Add protocol if missing
    if not website.startswith(('http://', 'https://')):
        website = f"https://{website}"
    
    try:
        parsed = urlparse(website)
        if parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    except:
        pass
    
    return ""


def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address."""
    if not email or '@' not in email:
        return ""
    
    try:
        return email.split('@')[1].lower()
    except:
        return ""


def extract_domain_from_website(website: str) -> str:
    """Extract domain from website URL."""
    if not website:
        return ""
    
    try:
        parsed = urlparse(website)
        return parsed.netloc.lower()
    except:
        return ""


def generate_unique_id(prefix: str = "") -> str:
    """Generate a unique identifier."""
    unique_id = str(uuid.uuid4())
    return f"{prefix}_{unique_id}" if prefix else unique_id


def generate_hash(data: Union[str, Dict[str, Any]]) -> str:
    """Generate SHA256 hash of data."""
    if isinstance(data, dict):
        # Sort keys for consistent hashing
        data_str = str(sorted(data.items()))
    else:
        data_str = str(data)
    
    return hashlib.sha256(data_str.encode()).hexdigest()


def random_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> None:
    """Add random delay between operations to avoid rate limiting."""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def get_current_timestamp() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def format_timestamp(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """Format datetime object as string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse timestamp string to datetime object."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def truncate_text(text: str, max_length: int = 255, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_get_nested(data: Dict[str, Any], keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation."""
    try:
        for key in keys.split('.'):
            data = data[key]
        return data
    except (KeyError, TypeError, AttributeError):
        return default


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flatten nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)