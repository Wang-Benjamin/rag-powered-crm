"""
Enhanced data type detection for CSV columns.
"""

import pandas as pd
import re
import logging
from typing import Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


class TypeDetector:
    """Enhanced intelligent data type detection for CSV columns."""
    
    @staticmethod
    def detect_column_type(series: pd.Series, column_name: str) -> Tuple[str, str]:
        """
        Detect the SQL data type for a pandas series.
        Returns (sql_type, pandas_type)
        """
        # Skip if all values are null
        if series.isna().all():
            return TypeDetector._infer_from_name(column_name)
        
        # For 'code' columns, check ALL unique values for mixed types
        if 'code' in column_name.lower():
            sample = series.dropna()  # Use all data for code columns
        else:
            # For numeric detection, use larger sample to avoid range issues
            sample = series.dropna().head(5000)  # Increased sample size
        
        # Try numeric detection first (before boolean to avoid misclassification)
        if TypeDetector._is_numeric(sample):
            # For columns with 'code' in the name, check for mixed data types FIRST
            if 'code' in column_name.lower():
                # Check for mixed data types FIRST
                if TypeDetector._has_mixed_data_types(sample):
                    return 'VARCHAR(100)', 'object'  # Handle mixed data as text
                elif TypeDetector._is_integer(sample):
                    numeric_sample = pd.to_numeric(sample, errors='coerce').dropna()
                    if len(numeric_sample) > 0:
                        max_val = numeric_sample.max()
                        min_val = numeric_sample.min()
                        if min_val >= -32768 and max_val <= 32767:
                            return 'SMALLINT', 'int16'
                        elif min_val >= -2147483648 and max_val <= 2147483647:
                            return 'INTEGER', 'int32'
                        else:
                            return 'BIGINT', 'int64'
                    else:
                        return 'INTEGER', 'int32'  # Default for code fields
                else:
                    return 'DECIMAL(10,2)', 'float64'
            
            # For other numeric fields, check if integer or decimal
            if TypeDetector._is_integer(sample):
                numeric_sample = pd.to_numeric(sample, errors='coerce').dropna()
                if len(numeric_sample) > 0:
                    max_val = numeric_sample.max()
                    min_val = numeric_sample.min()
                    # Be more conservative with integer types to avoid range errors
                    # Skip SMALLINT for sales data which often has large numbers
                    if min_val >= -2147483648 and max_val <= 2147483647:
                        return 'INTEGER', 'int32'
                    else:
                        return 'BIGINT', 'int64'
                else:
                    return 'BIGINT', 'int64'  # Default if no valid numeric values
            else:
                # Determine precision for decimal
                precision = TypeDetector._get_decimal_precision(sample)
                if precision[1] == 0:  # No decimal places
                    return 'BIGINT', 'int64'  # Use BIGINT for safety
                elif precision[1] <= 2:  # Money/currency likely
                    # Use more generous precision for decimal values
                    total_precision = max(precision[0], 15)  # At least 15 digits total
                    decimal_places = min(precision[1], 4)    # Up to 4 decimal places
                    return f'DECIMAL({total_precision},{decimal_places})', 'float64'
                else:
                    return 'DOUBLE PRECISION', 'float64'
        
        # For non-code columns, also check for mixed types
        if not ('code' in column_name.lower()):
            # For non-code columns, also check for mixed types
            if TypeDetector._has_mixed_data_types(sample):
                max_length = sample.astype(str).str.len().max()
                if max_length <= 50:
                    return 'VARCHAR(100)', 'object'
                elif max_length <= 255:
                    return 'VARCHAR(500)', 'object'
                else:
                    return 'TEXT', 'object'

        # Try boolean detection (only for non-numeric data or specific boolean indicators)
        if TypeDetector._is_boolean(sample, column_name):
            return 'BOOLEAN', 'bool'
        
        # Try date/datetime detection
        date_type = TypeDetector._detect_date_type(sample, column_name)
        if date_type:
            return date_type
        
        # Try JSON detection
        if TypeDetector._is_json(sample):
            return 'JSONB', 'object'
        
        # Default to text with appropriate length
        max_length = sample.astype(str).str.len().max()
        if max_length <= 50:
            return 'VARCHAR(100)', 'object'  # More generous sizing
        elif max_length <= 255:
            return 'VARCHAR(500)', 'object'  # More generous sizing
        else:
            return 'TEXT', 'object'
    
    @staticmethod
    def _infer_from_name(column_name: str) -> Tuple[str, str]:
        """Infer type from column name when data is missing."""
        name_lower = column_name.lower()
        
        # Code fields should be numeric
        if 'code' in name_lower:
            return 'INTEGER', 'int32'
        
        # Boolean indicators
        if any(indicator in name_lower for indicator in ['is_', 'has_', 'flag', 'active', 'enabled']):
            return 'BOOLEAN', 'bool'
        
        # Date/time indicators
        if any(indicator in name_lower for indicator in ['date', 'time', 'created', 'updated', 'modified']):
            if 'time' in name_lower and 'date' not in name_lower:
                return 'TIME', 'object'
            elif any(indicator in name_lower for indicator in ['timestamp', 'datetime', 'created_at', 'updated_at']):
                return 'TIMESTAMP', 'datetime64[ns]'
            else:
                return 'DATE', 'datetime64[ns]'
        
        # Numeric indicators - enhanced for sales datasets
        if any(indicator in name_lower for indicator in ['amount', 'price', 'cost', 'total', 'sum', 'count', 'quantity', 'sales', 'revenue', 'profit', 'value']):
            if any(indicator in name_lower for indicator in ['count', 'quantity', 'qty', 'ordered', 'sold']):
                return 'BIGINT', 'int64'  # Use BIGINT for quantities to avoid overflow
            else:
                return 'DECIMAL(15,2)', 'float64'  # More generous precision for sales amounts
        
        # ID fields
        if any(indicator in name_lower for indicator in ['_id', 'number']):
            return 'VARCHAR(100)', 'object'  # More generous sizing for codes
        
        # Description/text fields
        if any(indicator in name_lower for indicator in ['description', 'notes', 'comment', 'message']):
            return 'TEXT', 'object'
        
        # Default
        return 'VARCHAR(255)', 'object'
    
    @staticmethod
    def _is_boolean(series: pd.Series, column_name: str = "") -> bool:
        """Check if series contains boolean values - with stricter criteria."""
        unique_values = series.dropna().unique()
        
        # Must have at most 2 unique values for boolean
        if len(unique_values) > 2:
            return False
        
        # If column name contains 'code', 'id', 'number', or other numeric indicators, treat as numeric
        name_lower = column_name.lower()
        numeric_indicators = ['code', 'id', 'number', 'amount', 'price', 'cost', 'value', 'rate', 'score', 'rep']
        if any(indicator in name_lower for indicator in numeric_indicators):
            return False
        
        # If all values are numeric and not explicitly boolean indicators, treat as numeric
        all_numeric = True
        for val in unique_values:
            if not isinstance(val, (int, float, bool)) and not (isinstance(val, str) and val.replace('.', '').replace('-', '').isdigit()):
                all_numeric = False
                break
        
        if all_numeric:
            # Only treat as boolean if column name suggests boolean
            boolean_indicators = ['is_', 'has_', 'flag', 'active', 'enabled', 'valid', 'confirmed']
            if not any(indicator in name_lower for indicator in boolean_indicators):
                return False
        
        # Check for explicit boolean representations
        bool_values = {
            'true', 'false', 't', 'f', 'yes', 'no', 'y', 'n', 
            'TRUE', 'FALSE', 'True', 'False'
        }
        
        # String representations that should be boolean (excluding pure numbers)
        string_bool_values = bool_values
        
        # Check each unique value
        for val in unique_values:
            if pd.isna(val):
                continue
            elif isinstance(val, bool):
                continue
            elif isinstance(val, str) and val in string_bool_values:
                continue
            elif isinstance(val, (int, float)) and val in [0, 1] and any(indicator in name_lower for indicator in ['is_', 'has_', 'flag', 'active', 'enabled']):
                # Only accept 0/1 as boolean if column name explicitly suggests boolean
                continue
            else:
                return False
        
        return True
    
    @staticmethod
    def _is_numeric(series: pd.Series) -> bool:
        """Check if series contains numeric values - TEXT-FIRST strategy."""
        # TEXT-FIRST: If ANY value contains alphabetic characters, treat as TEXT
        try:
            # Check first 1000 non-null values for alphabetic characters
            sample_count = 0
            for value in series:
                if pd.isna(value) or value == '' or value == 'nan':
                    continue
                
                sample_count += 1
                if sample_count > 1000:
                    break
                
                # Convert to string to check for alphabetic characters
                str_value = str(value).strip()
                if not str_value:
                    continue
                    
                # If the value contains any alphabetic characters, it's not purely numeric
                if any(c.isalpha() for c in str_value):
                    return False
                
                # Also check for mixed alphanumeric patterns like "R05699"
                # If it starts with a letter followed by numbers, it's an identifier
                if len(str_value) > 1 and str_value[0].isalpha() and any(c.isdigit() for c in str_value[1:]):
                    return False
            
            # If we get here, no alphabetic characters were found
            # Now check if values are actually numeric
            try:
                pd.to_numeric(series, errors='raise')
                return True
            except:
                # Try coercing and see if most values are numeric
                try:
                    numeric_series = pd.to_numeric(series, errors='coerce')
                    non_null_count = series.dropna().shape[0]
                    numeric_count = numeric_series.dropna().shape[0]
                    
                    # If >90% of values are numeric, consider it numeric
                    if non_null_count > 0 and (numeric_count / non_null_count) > 0.9:
                        return True
                    return False
                except:
                    return False
                    
        except Exception as e:
            logger.debug(f"Error in _is_numeric: {e}")
            return False
    
    @staticmethod
    def _is_integer(series: pd.Series) -> bool:
        """Check if numeric series contains only integers."""
        try:
            numeric_series = pd.to_numeric(series, errors='coerce').dropna()
            if len(numeric_series) == 0:
                return False
            
            # Check if all numeric values are integers
            return all(val == int(val) for val in numeric_series if pd.notna(val))
        except:
            return False
    
    @staticmethod
    def _get_decimal_precision(series: pd.Series) -> Tuple[int, int]:
        """Get precision and scale for decimal values."""
        try:
            max_total_digits = 0
            max_decimal_digits = 0
            
            numeric_series = pd.to_numeric(series, errors='coerce').dropna()
            
            for val in numeric_series:
                if pd.notna(val):
                    str_val = str(float(val))
                    if '.' in str_val:
                        parts = str_val.split('.')
                        total_digits = len(parts[0]) + len(parts[1].rstrip('0'))
                        decimal_digits = len(parts[1].rstrip('0'))
                    else:
                        total_digits = len(str_val)
                        decimal_digits = 0
                    
                    max_total_digits = max(max_total_digits, total_digits)
                    max_decimal_digits = max(max_decimal_digits, decimal_digits)
            
            return max_total_digits, max_decimal_digits
        except:
            return 10, 2  # Default precision
    
    @staticmethod
    def _has_mixed_data_types(series: pd.Series) -> bool:
        """Check if series has mixed data types (numeric and text)."""
        try:
            sample_values = series.dropna().head(1000)  # Sample for performance
            
            if len(sample_values) == 0:
                return False
            
            has_numeric = False
            has_text = False
            
            for value in sample_values:
                str_value = str(value).strip()
                
                # Check if it's numeric
                try:
                    float(str_value)
                    has_numeric = True
                except ValueError:
                    # Check if it contains alphabetic characters (text)
                    if any(c.isalpha() for c in str_value):
                        has_text = True
            
            # If we found both types, it's mixed
            if has_numeric and has_text:
                return True
        
        except Exception:
            # If there's an error in analysis, assume not mixed
            return False
        
        return False
    
    @staticmethod
    def _detect_date_type(series: pd.Series, column_name: str) -> Tuple[str, str]:
        """Detect date/datetime types."""
        name_lower = column_name.lower()
        
        # Quick check based on column name
        if not any(indicator in name_lower for indicator in ['date', 'time', 'created', 'updated', 'modified']):
            return None
        
        try:
            # Try to parse a sample as dates
            sample = series.dropna().head(100)
            if len(sample) == 0:
                return None
            
            # Try pandas date parsing
            try:
                parsed_dates = pd.to_datetime(sample, errors='coerce')
                successful_parses = parsed_dates.dropna()
                
                # If >70% of values parsed as dates, it's likely a date column
                if len(successful_parses) / len(sample) > 0.7:
                    # Check if times are present
                    has_time = any('time' in name_lower for indicator in ['time', 'timestamp', 'datetime'])
                    if has_time:
                        return 'TIMESTAMP', 'datetime64[ns]'
                    else:
                        return 'DATE', 'datetime64[ns]'
            except:
                pass
            
        except Exception as e:
            logger.debug(f"Error in date detection: {e}")
        
        return None
    
    @staticmethod
    def _is_json(series: pd.Series) -> bool:
        """Check if series contains JSON data."""
        try:
            sample = series.dropna().head(10)
            if len(sample) == 0:
                return False
            
            json_count = 0
            for value in sample:
                str_value = str(value).strip()
                if str_value.startswith(('{', '[')) and str_value.endswith(('}', ']')):
                    try:
                        import json
                        json.loads(str_value)
                        json_count += 1
                    except:
                        pass
            
            # If >50% of values are valid JSON, consider it a JSON column
            return json_count / len(sample) > 0.5
        except:
            return False