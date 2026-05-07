"""
File analysis service for CSV mapping.
Refactored to work as a library component without FastAPI dependencies.
"""

import os
import tempfile
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union, IO
from ..models.mapping_models import FileMetadata, ColumnAnalysis, DataIssue
from ..utils.type_detector import TypeDetector

logger = logging.getLogger(__name__)


class FileAnalyzer:
    """Enhanced file analysis with encoding detection and data quality assessment."""
    
    # File validation constants
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    
    @staticmethod
    def analyze_file(
        file_input: Union[str, Path, pd.DataFrame, IO], 
        filename: Optional[str] = None
    ) -> Tuple[pd.DataFrame, FileMetadata]:
        """
        Analyze file or DataFrame and return DataFrame with metadata.
        
        Args:
            file_input: Can be:
                - String path to file
                - Path object
                - pandas DataFrame (returns as-is with generated metadata)
                - File-like object (IO)
            filename: Optional filename for metadata (required for file objects)
            
        Returns:
            Tuple of (DataFrame, FileMetadata)
        """
        if isinstance(file_input, pd.DataFrame):
            # Input is already a DataFrame
            return FileAnalyzer._analyze_dataframe(file_input, filename or "dataframe")
        
        elif isinstance(file_input, (str, Path)):
            # Input is a file path
            file_path = Path(file_input)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            return FileAnalyzer._analyze_file_path(file_path)
        
        elif hasattr(file_input, 'read'):
            # Input is a file-like object
            if not filename:
                raise ValueError("filename parameter is required when using file objects")
            
            return FileAnalyzer._analyze_file_object(file_input, filename)
        
        else:
            raise ValueError("file_input must be a file path, DataFrame, or file-like object")
    
    @staticmethod
    def _analyze_dataframe(df: pd.DataFrame, filename: str) -> Tuple[pd.DataFrame, FileMetadata]:
        """Analyze an existing DataFrame."""
        file_metadata = FileMetadata(
            filename=filename,
            size_bytes=df.memory_usage(deep=True).sum(),  # Approximate memory usage
            encoding="utf-8",  # Assume UTF-8 for DataFrames
            row_count=len(df),
            column_count=len(df.columns),
            detected_separator=",",  # Not applicable for DataFrames
            has_header=True
        )
        
        return df, file_metadata
    
    @staticmethod
    def _analyze_file_path(file_path: Path) -> Tuple[pd.DataFrame, FileMetadata]:
        """Analyze a file given its path."""
        # Validate file extension
        file_ext = file_path.suffix.lower()
        if file_ext not in FileAnalyzer.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {file_ext} not allowed. Allowed types: {', '.join(FileAnalyzer.ALLOWED_EXTENSIONS)}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > FileAnalyzer.MAX_FILE_SIZE:
            raise ValueError(f"File too large. Maximum size is {FileAnalyzer.MAX_FILE_SIZE/1024/1024}MB")
        
        # Detect file encoding
        encoding = FileAnalyzer.detect_file_encoding(str(file_path))
        
        # Load file into DataFrame
        df, separator = FileAnalyzer.load_file_to_dataframe(str(file_path), encoding)
        
        # Create file metadata
        file_metadata = FileMetadata(
            filename=file_path.name,
            size_bytes=file_size,
            encoding=encoding,
            row_count=len(df),
            column_count=len(df.columns),
            detected_separator=separator,
            has_header=True  # Assume header for now
        )
        
        return df, file_metadata
    
    @staticmethod
    def _analyze_file_object(file_obj: IO, filename: str) -> Tuple[pd.DataFrame, FileMetadata]:
        """Analyze a file-like object by saving it to a temporary file."""
        # Validate file extension from filename
        file_ext = Path(filename).suffix.lower()
        if file_ext not in FileAnalyzer.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {file_ext} not allowed. Allowed types: {', '.join(FileAnalyzer.ALLOWED_EXTENSIONS)}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            temp_path = tmp_file.name
            
            # Copy file content to temporary file
            try:
                file_obj.seek(0)  # Ensure we read from the beginning
                total_size = 0
                
                while True:
                    chunk = file_obj.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    
                    if isinstance(chunk, str):
                        chunk = chunk.encode('utf-8')
                    
                    total_size += len(chunk)
                    if total_size > FileAnalyzer.MAX_FILE_SIZE:
                        raise ValueError(f"File too large. Maximum size is {FileAnalyzer.MAX_FILE_SIZE/1024/1024}MB")
                    
                    tmp_file.write(chunk)
                
                tmp_file.flush()
                
                # Analyze the temporary file
                temp_path_obj = Path(temp_path)
                df, file_metadata = FileAnalyzer._analyze_file_path(temp_path_obj)
                
                # Update metadata with original filename and actual size
                file_metadata.filename = filename
                file_metadata.size_bytes = total_size
                
                return df, file_metadata
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.warning(f"Failed to delete temp file: {temp_path}")
    
    @staticmethod
    def detect_file_encoding(file_path: str) -> str:
        """
        Detect the encoding of a file using multiple strategies.
        Enhanced from original with better fallback handling.
        """
        # Try charset-normalizer first if available
        try:
            import charset_normalizer
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            result = charset_normalizer.from_bytes(raw_data)
            if result:
                best_result = result.best()
                if best_result and best_result.encoding:
                    encoding = str(best_result.encoding)
                    logger.info(f"Detected encoding using charset-normalizer: {encoding}")
                    return encoding
        except ImportError:
            logger.debug("charset-normalizer not available, using fallback detection")
        except Exception as e:
            logger.debug(f"charset-normalizer failed: {e}")
        
        # Fallback: Try common encodings in order of likelihood
        common_encodings = [
            'utf-8',
            'windows-1252',  # Common for CSV files from Windows/Excel
            'latin-1',       # ISO-8859-1, very permissive
            'cp1252',        # Windows Western European
            'utf-16',        # Sometimes used by Excel
        ]
        
        for encoding in common_encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    # Try to read the first 1MB to test encoding
                    f.read(1024 * 1024)
                logger.info(f"Successfully detected encoding: {encoding}")
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                logger.debug(f"Error testing encoding {encoding}: {e}")
                continue
        
        # Last resort: use utf-8 with error handling
        logger.warning("Could not detect encoding reliably, falling back to utf-8 with error replacement")
        return 'utf-8'
    
    @staticmethod
    def load_file_to_dataframe(file_path: str, encoding: str) -> Tuple[pd.DataFrame, str]:
        """
        Load file into pandas DataFrame with separator detection.
        
        Args:
            file_path: Path to the file
            encoding: File encoding to use
            
        Returns:
            Tuple of (DataFrame, detected_separator)
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.xlsx', '.xls']:
            # Excel files
            df = pd.read_excel(file_path)
            return df, ","  # Excel doesn't use separators
        
        else:
            # CSV files - detect separator
            separator = FileAnalyzer._detect_csv_separator(file_path, encoding)
            
            try:
                df = pd.read_csv(
                    file_path, 
                    encoding=encoding,
                    sep=separator,
                    on_bad_lines='skip'  # Skip malformed lines
                )
                return df, separator
                
            except Exception as e:
                logger.error(f"Failed to read CSV with separator '{separator}': {e}")
                # Try with default separator
                try:
                    df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
                    return df, ","
                except Exception as e2:
                    raise ValueError(f"Failed to read file: {e2}")
    
    @staticmethod
    def _detect_csv_separator(file_path: str, encoding: str) -> str:
        """Detect CSV separator by analyzing first few lines."""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_lines = [f.readline() for _ in range(3)]
            
            # Count occurrences of common separators
            separators = [',', ';', '\t', '|']
            separator_counts = {}
            
            for sep in separators:
                counts = [line.count(sep) for line in first_lines if line.strip()]
                if counts:
                    # Check if separator count is consistent across lines
                    if len(set(counts)) <= 2:  # Allow some variation
                        separator_counts[sep] = sum(counts)
            
            if separator_counts:
                # Return separator with highest count
                return max(separator_counts, key=separator_counts.get)
            
        except Exception as e:
            logger.warning(f"Separator detection failed: {e}")
        
        return ","  # Default to comma
    
    @staticmethod
    def analyze_columns(df: pd.DataFrame) -> List[ColumnAnalysis]:
        """
        Analyze DataFrame columns for type detection and data quality.
        
        Args:
            df: Input DataFrame
            
        Returns:
            List of ColumnAnalysis objects
        """
        analyses = []
        
        for position, column in enumerate(df.columns):  # Track position
            series = df[column]
            
            # Detect data type
            sql_type, pandas_type = TypeDetector.detect_column_type(series, column)
            
            # Calculate statistics
            null_count = series.isnull().sum()
            null_percentage = (null_count / len(series)) * 100 if len(series) > 0 else 0
            unique_count = series.nunique()
            
            # Get sample values (non-null, converted to strings)
            sample_values = []
            non_null_series = series.dropna()
            if len(non_null_series) > 0:
                sample_size = min(5, len(non_null_series))
                sample_values = [str(val) for val in non_null_series.head(sample_size).tolist()]
            
            # Assess data quality issues
            quality_issues = FileAnalyzer._assess_column_quality(series, column)
            
            # Calculate confidence score based on data quality
            confidence_score = FileAnalyzer._calculate_column_confidence(
                null_percentage, unique_count, len(series), quality_issues
            )
            
            analysis = ColumnAnalysis(
                name=column,
                original_position=position,  # Add position tracking
                detected_type=sql_type,
                pandas_type=pandas_type,
                sample_values=sample_values,
                null_percentage=null_percentage,
                unique_count=unique_count,
                confidence_score=confidence_score,
                data_quality_issues=[issue["description"] for issue in quality_issues]
            )
            
            analyses.append(analysis)
        
        return analyses
    
    @staticmethod
    def _assess_column_quality(series: pd.Series, column_name: str) -> List[Dict[str, Any]]:
        """Assess data quality issues for a column."""
        issues = []
        
        # Check for high null percentage
        null_percentage = (series.isnull().sum() / len(series)) * 100
        if null_percentage > 50:
            issues.append({
                "type": "null_values",
                "description": f"High null percentage: {null_percentage:.1f}%",
                "severity": "high" if null_percentage > 80 else "medium"
            })
        
        # Check for inconsistent data types
        non_null_series = series.dropna()
        if len(non_null_series) > 0:
            # Sample values for type consistency check
            sample_types = set()
            for val in non_null_series.head(100):
                if isinstance(val, (int, float)):
                    sample_types.add("numeric")
                elif isinstance(val, str):
                    sample_types.add("string")
                elif isinstance(val, bool):
                    sample_types.add("boolean")
                else:
                    sample_types.add("other")
            
            if len(sample_types) > 1:
                issues.append({
                    "type": "type_inconsistency",
                    "description": f"Mixed data types detected: {', '.join(sample_types)}",
                    "severity": "medium"
                })
        
        # Check for extremely low cardinality (potential data quality issue)
        unique_count = series.nunique()
        if unique_count == 1 and len(series) > 10:
            issues.append({
                "type": "low_cardinality",
                "description": "Column has only one unique value",
                "severity": "low"
            })
        
        return issues
    
    @staticmethod
    def _calculate_column_confidence(
        null_percentage: float, 
        unique_count: int, 
        total_count: int,
        quality_issues: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for column type detection."""
        base_confidence = 80.0
        
        # Penalty for high null percentage
        if null_percentage > 50:
            base_confidence -= 20.0
        elif null_percentage > 20:
            base_confidence -= 10.0
        
        # Penalty for quality issues
        for issue in quality_issues:
            severity = issue.get("severity", "low")
            if severity == "high":
                base_confidence -= 15.0
            elif severity == "medium":
                base_confidence -= 10.0
            else:
                base_confidence -= 5.0
        
        # Bonus for good cardinality
        if total_count > 0:
            cardinality_ratio = unique_count / total_count
            if 0.1 <= cardinality_ratio <= 0.9:  # Good diversity
                base_confidence += 5.0
        
        return min(100.0, max(0.0, base_confidence))
    
    @staticmethod
    def generate_data_issues(df: pd.DataFrame, analyses: List[ColumnAnalysis]) -> List[DataIssue]:
        """Generate comprehensive data quality issues report."""
        issues = []
        
        for analysis in analyses:
            column = analysis.name
            
            # Null value issues
            if analysis.null_percentage > 10:
                severity = "high" if analysis.null_percentage > 50 else "medium"
                
                issues.append(DataIssue(
                    type="null_values",
                    column=column,
                    description=f"Column '{column}' has {analysis.null_percentage:.1f}% null values",
                    count=int(len(df) * analysis.null_percentage / 100),
                    percentage=analysis.null_percentage,
                    severity=severity,
                    suggested_action="Review data source or consider default values" if severity == "high" else None
                ))
            
            # Low cardinality issues
            if analysis.unique_count == 1 and len(df) > 10:
                issues.append(DataIssue(
                    type="low_cardinality",
                    column=column,
                    description=f"Column '{column}' has only one unique value",
                    count=1,
                    percentage=100.0,
                    severity="low",
                    suggested_action="Consider if this column is needed"
                ))
        
        return issues
    
    @staticmethod
    def analyze_file_complete(
        file_input: Union[str, Path, pd.DataFrame, IO], 
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete file analysis returning DataFrame, metadata, column analyses, and data issues.
        
        Args:
            file_input: Can be:
                - String path to file
                - Path object  
                - pandas DataFrame
                - File-like object (IO)
            filename: Optional filename for metadata (required for file objects)
            
        Returns:
            Dictionary containing:
                - dataframe: The loaded pandas DataFrame
                - metadata: FileMetadata object
                - column_analyses: List of ColumnAnalysis objects
                - data_issues: List of DataIssue objects
        """
        try:
            # Analyze the file/dataframe
            df, file_metadata = FileAnalyzer.analyze_file(file_input, filename)
            
            # Analyze columns
            column_analyses = FileAnalyzer.analyze_columns(df)
            
            # Generate data issues
            data_issues = FileAnalyzer.generate_data_issues(df, column_analyses)
            
            return {
                "dataframe": df,
                "metadata": file_metadata,
                "column_analyses": column_analyses,
                "data_issues": data_issues
            }
            
        except Exception as e:
            logger.error(f"Complete file analysis failed: {e}")
            raise