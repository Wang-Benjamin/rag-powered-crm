"""Upload router for CRM customer import functionality."""

import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

import asyncpg
from service_core.db import get_tenant_connection

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

# Try to import CSV mapping library
CSV_MAPPING_AVAILABLE = False
try:
    from csv_mapping import (
        CSVMapper, DatabaseConfig, MappingConfig,
        TableSchema, TableColumn, AnalysisResult
    )
    CSV_MAPPING_AVAILABLE = True
except ImportError as e:
    pass

logger = logging.getLogger(__name__)

router = APIRouter()

# Schemas for CSV upload functionality
class RecommendedFlow(str, Enum):
    """Recommended UI flow based on confidence."""
    QUICK_UPLOAD = "QUICK_UPLOAD"
    SHOW_MAPPING_UI = "SHOW_MAPPING_UI"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"


class SourceColumnInfo(BaseModel):
    """Source column analysis info."""
    name: str
    original_position: int
    data_type: str
    sample_values: List[Any] = Field(default_factory=list)
    null_percentage: float = 0.0


class MappingSuggestionInfo(BaseModel):
    """Column mapping suggestion with confidence."""
    source_column: str
    target_column: Optional[str] = None
    confidence: float = Field(ge=0, le=100, description="Confidence score 0-100")
    mapping_type: str = "PATTERN"


class CustomerUploadResponse(BaseModel):
    message: str
    filename: str
    total_rows: int
    inserted_rows: int
    failed_rows: int
    skipped_rows: int = 0
    columns_detected: List[str]
    processing_time_ms: float
    warnings: Optional[List[str]] = None


class ColumnMappingResponse(BaseModel):
    success: bool
    filename: str
    source_columns: List[str]
    suggested_mappings: Dict[str, str]
    crm_fields: List[str]
    message: str
    # New fields for confidence scoring
    mapping_suggestions: List[MappingSuggestionInfo] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    recommended_flow: RecommendedFlow = RecommendedFlow.REQUIRE_REVIEW
    source_columns_info: List[SourceColumnInfo] = Field(default_factory=list)


class CustomerImportPreview(BaseModel):
    success: bool
    filename: str
    preview_data: List[Dict[str, Any]]
    column_mapping: Dict[str, str]
    total_rows: int
    ready_for_import: bool

# Standard CRM customer fields for mapping
CRM_CUSTOMER_FIELDS = {
    'company': 'Company Name',
    'primaryContact': 'Primary Contact',
    'email': 'Email Address',
    'phone': 'Phone Number',
    'location': 'Location',
    'status': 'Status',
    'clientType': 'Client Type',
    'healthScore': 'Health Score',
}

async def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file to temporary location."""
    import tempfile

    # Create temp file with original extension
    file_ext = Path(upload_file.filename).suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)

    try:
        # Read file content and write to temp file
        content = await upload_file.read()
        with open(temp_file.name, 'wb') as f:
            f.write(content)
        return temp_file.name
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        raise e

def detect_file_encoding(file_path: str) -> str:
    """Detect file encoding for CSV files."""
    if not CHARDET_AVAILABLE:
        return 'utf-8'

    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    except Exception as e:
        logger.warning(f"Encoding detection failed, using utf-8: {e}")
        return 'utf-8'

def suggest_column_mappings_with_confidence(source_columns: List[str]) -> tuple[Dict[str, str], List[MappingSuggestionInfo]]:
    """Suggest mappings between source columns and CRM fields using fuzzy matching.

    Returns a tuple of:
    - Dict where keys are ORIGINAL source column names and values are the target CRM field names
    - List of MappingSuggestionInfo with confidence scores
    """
    mappings = {}
    suggestions = []

    # Define mapping patterns (enhanced with more variations)
    mapping_patterns = {
        'company': [
            'company', 'company_name', 'companyname', 'organization', 'org', 'business',
            'firm', 'business_name', 'account', 'customer_name', 'client_name',
            'organisation', 'corp', 'corporation'
        ],
        'primaryContact': [
            'contact', 'primary_contact', 'primarycontact', 'main_contact', 'maincontact',
            'contact_name', 'contactname', 'name', 'full_name', 'fullname',
            'contact_person', 'person', 'representative', 'rep', 'owner'
        ],
        'email': [
            'email', 'email_address', 'emailaddress', 'e_mail', 'mail',
            'contact_email', 'primary_email', 'email_id', 'emailid'
        ],
        'phone': [
            'phone', 'phone_number', 'phonenumber', 'tel', 'telephone',
            'mobile', 'cell', 'contact_number', 'contactnumber',
            'phone_no', 'phoneno', 'tel_no', 'telno'
        ],
        'location': [
            'location', 'address', 'city', 'state', 'country', 'region',
            'area', 'place', 'locality', 'territory', 'geography'
        ],
        'status': [
            'status', 'customer_status', 'customerstatus', 'account_status', 'accountstatus',
            'state', 'condition', 'active_status', 'client_status'
        ],
        'clientType': [
            'client_type', 'clienttype', 'customer_type', 'customertype', 'type',
            'category', 'classification', 'segment', 'tier', 'level'
        ],
        'arr': [
            'arr', 'annual_revenue', 'annualrevenue', 'yearly_revenue', 'yearlyrevenue',
            'annual_recurring_revenue', 'annualrecurringrevenue', 'yearly_income',
            'annual_income', 'revenue_annual', 'revenue_yearly'
        ],
        'healthScore': [
            'health_score', 'healthscore', 'health', 'score', 'customer_health',
            'customerhealth', 'account_health', 'relationship_score'
        ]
    }

    used_targets = set()

    for source_col in source_columns:
        source_normalized = source_col.lower().replace('-', '_').replace(' ', '_')
        best_match = None
        best_confidence = 0
        mapping_type = "NONE"

        for crm_field, patterns in mapping_patterns.items():
            if crm_field in used_targets:
                continue

            # Exact match - high confidence
            if source_normalized in patterns:
                best_match = crm_field
                best_confidence = 95
                mapping_type = "EXACT"
                break

            # Partial match
            for pattern in patterns:
                if pattern in source_normalized or source_normalized in pattern:
                    score = max(len(pattern), len(source_normalized)) / (len(pattern) + len(source_normalized))
                    confidence = int(score * 80)  # Scale to 0-80 for partial matches
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = crm_field
                        mapping_type = "PATTERN"

        if best_match and best_confidence >= 50:
            mappings[source_col] = best_match
            used_targets.add(best_match)

        suggestions.append(MappingSuggestionInfo(
            source_column=source_col,
            target_column=best_match if best_confidence >= 50 else None,
            confidence=best_confidence,
            mapping_type=mapping_type
        ))

    return mappings, suggestions


def suggest_column_mappings(source_columns: List[str]) -> Dict[str, str]:
    """Legacy function for backward compatibility."""
    mappings, _ = suggest_column_mappings_with_confidence(source_columns)
    return mappings

def validate_customer_data(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean customer data before insertion."""
    cleaned_data = {}

    def is_valid_value(value):
        """Check if value is not None, NaN, or empty string"""
        if value is None:
            return False
        if pd.isna(value):
            return False
        if str(value).strip() == '':
            return False
        return True

    # Required fields
    if 'company' in row_data and is_valid_value(row_data['company']):
        cleaned_data['company'] = str(row_data['company']).strip()
    else:
        raise ValueError("Company name is required")

    if 'primaryContact' in row_data and is_valid_value(row_data['primaryContact']):
        cleaned_data['primaryContact'] = str(row_data['primaryContact']).strip()
    else:
        raise ValueError("Primary contact is required")

    if 'email' in row_data and is_valid_value(row_data['email']):
        email = str(row_data['email']).strip()
        # Basic email validation
        if '@' not in email:
            raise ValueError(f"Invalid email format: {email}")
        cleaned_data['email'] = email
    else:
        raise ValueError("Email is required")

    # Optional fields with defaults
    cleaned_data['phone'] = str(row_data.get('phone', '')).strip()
    cleaned_data['location'] = str(row_data.get('location', '')).strip()
    cleaned_data['status'] = str(row_data.get('status', 'active')).strip()
    cleaned_data['clientType'] = str(row_data.get('clientType', 'lead')).strip()

    # Numeric fields
    if 'healthScore' in row_data and row_data['healthScore']:
        try:
            cleaned_data['healthScore'] = float(row_data['healthScore'])
        except (ValueError, TypeError):
            cleaned_data['healthScore'] = 0.0
    else:
        cleaned_data['healthScore'] = 0.0

    return cleaned_data

@router.post("/analyze-csv", response_model=ColumnMappingResponse)
async def analyze_csv_for_mapping(
    file: UploadFile = File(...),
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
):
    """Analyze uploaded CSV/XLSX and suggest column mappings for CRM fields.

    Returns mapping suggestions with confidence scores and recommended UI flow.
    """
    temp_path = None

    try:
        # Validate file
        if not file.filename:
            raise ValueError("No filename provided")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in {'.csv', '.xlsx', '.xls'}:
            raise ValueError(f"File type {file_ext} not supported. Please upload CSV or Excel files.")

        # Save file temporarily
        temp_path = await save_upload_file(file)

        # Read file
        if file_ext == '.csv':
            detected_encoding = detect_file_encoding(temp_path)
            df = pd.read_csv(temp_path, encoding=detected_encoding, low_memory=False)
        else:
            df = pd.read_excel(temp_path)

        # Get source columns
        source_columns = list(df.columns)

        # Build source column info with sample data
        source_columns_info = []
        for i, col in enumerate(df.columns):
            null_pct = (df[col].isnull().sum() / len(df)) * 100 if len(df) > 0 else 0
            source_columns_info.append(SourceColumnInfo(
                name=col,
                original_position=i,
                data_type=str(df[col].dtype),
                sample_values=df[col].dropna().head(3).tolist(),
                null_percentage=round(null_pct, 2)
            ))

        # Suggest mappings with confidence scores
        suggested_mappings, mapping_suggestions = suggest_column_mappings_with_confidence(source_columns)

        # Calculate overall confidence
        if mapping_suggestions:
            matched = [s for s in mapping_suggestions if s.target_column]
            if matched:
                avg_confidence = sum(s.confidence for s in matched) / len(matched)
                overall_confidence = (len(matched) / len(source_columns)) * (avg_confidence / 100)
            else:
                overall_confidence = 0.0
        else:
            overall_confidence = 0.0

        # Determine recommended flow
        if overall_confidence >= 0.90:
            recommended_flow = RecommendedFlow.QUICK_UPLOAD
        elif overall_confidence >= 0.50:
            recommended_flow = RecommendedFlow.SHOW_MAPPING_UI
        else:
            recommended_flow = RecommendedFlow.REQUIRE_REVIEW

        # Get available CRM fields
        crm_fields = list(CRM_CUSTOMER_FIELDS.keys())

        return ColumnMappingResponse(
            success=True,
            filename=file.filename,
            source_columns=source_columns,
            suggested_mappings=suggested_mappings,
            crm_fields=crm_fields,
            message=f"Found {len(source_columns)} columns, suggested {len(suggested_mappings)} mappings",
            mapping_suggestions=mapping_suggestions,
            overall_confidence=overall_confidence,
            recommended_flow=recommended_flow,
            source_columns_info=source_columns_info
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"CSV analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"CSV analysis failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

@router.post("/preview-import", response_model=CustomerImportPreview)
async def preview_customer_import(
    file: UploadFile = File(...),
    column_mapping: str = Form(..., description="JSON string of column mappings"),
    sample_size: int = Form(10, ge=1, le=50, description="Number of rows to preview"),
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
):
    """Preview customer data with applied column mappings."""
    temp_path = None

    try:
        # Parse column mapping
        try:
            mappings = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise ValueError("Invalid column mapping JSON")

        # Save and read file
        temp_path = await save_upload_file(file)
        file_ext = Path(file.filename).suffix.lower()

        if file_ext == '.csv':
            detected_encoding = detect_file_encoding(temp_path)
            df = pd.read_csv(temp_path, encoding=detected_encoding, low_memory=False)
        else:
            df = pd.read_excel(temp_path)

        # Apply column mapping
        mapped_df = df.rename(columns=mappings)

        # Get preview data
        preview_df = mapped_df.head(sample_size)

        # Convert to list of dictionaries for JSON response
        preview_data = []
        for _, row in preview_df.iterrows():
            row_dict = {}
            for col in preview_df.columns:
                value = row[col]
                # Handle NaN values
                if pd.isna(value):
                    row_dict[col] = ""
                else:
                    row_dict[col] = str(value)
            preview_data.append(row_dict)

        # Check if ready for import (has required fields)
        required_fields = {'company', 'primaryContact', 'email'}
        mapped_columns = set(mapped_df.columns)
        ready_for_import = required_fields.issubset(mapped_columns)

        return CustomerImportPreview(
            success=True,
            filename=file.filename,
            preview_data=preview_data,
            column_mapping=mappings,
            total_rows=len(df),
            ready_for_import=ready_for_import
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Import preview failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import preview failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

@router.post("/import-customers", response_model=CustomerUploadResponse)
async def import_customers(
    file: UploadFile = File(...),
    column_mapping: str = Form(..., description="JSON string of column mappings"),
    skip_duplicates: bool = Form(True, description="Skip rows with duplicate emails"),
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
):
    """Import customers from CSV/XLSX file with column mapping."""
    temp_path = None
    start_time = datetime.now(timezone.utc)
    conn, user = tenant

    logger.info(f"Starting CSV import for file: {file.filename}")

    try:
        # Parse column mapping
        try:
            mappings = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise ValueError("Invalid column mapping JSON")

        # Save and read file
        temp_path = await save_upload_file(file)
        file_ext = Path(file.filename).suffix.lower()

        if file_ext == '.csv':
            detected_encoding = detect_file_encoding(temp_path)
            df = pd.read_csv(temp_path, encoding=detected_encoding, low_memory=False)
        else:
            df = pd.read_excel(temp_path)

        # Apply column mapping
        mapped_df = df.rename(columns=mappings)

        # Validate required fields
        required_fields = {'company', 'primaryContact', 'email'}
        mapped_columns = set(mapped_df.columns)
        if not required_fields.issubset(mapped_columns):
            missing = required_fields - mapped_columns
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Process data
        inserted_rows = 0
        failed_rows = 0
        skipped_rows = 0
        warnings = []
        existing_emails = set()

        # Get existing emails if skip_duplicates is enabled
        if skip_duplicates:
            try:
                rows = await conn.fetch("SELECT DISTINCT email FROM personnel WHERE client_id IS NOT NULL AND email IS NOT NULL")
                existing_emails = {row["email"].lower() for row in rows if row["email"]}
            except Exception as e:
                logger.warning(f"Could not fetch existing emails: {e}")

        # Process each row
        for index, row in mapped_df.iterrows():
            try:
                logger.info(f"Processing row {index + 1}/{len(mapped_df)}")

                # Convert row to dict and validate
                row_data = row.to_dict()

                # Skip if duplicate email
                if skip_duplicates and 'email' in row_data:
                    email = str(row_data['email']).strip().lower()
                    if email in existing_emails:
                        logger.info(f"Skipping row {index + 1}: duplicate email {email}")
                        skipped_rows += 1
                        continue

                # Validate and clean data
                cleaned_data = validate_customer_data(row_data)

                # Insert customer - DB auto-generates client_id
                result = await conn.fetchrow("""
                    INSERT INTO clients (
                        name, phone,
                        location, source, created_at, updated_at, notes,
                        health_score, stage, status
                    ) VALUES (
                        $1, $2, $3, $4, NOW(), NOW(), '', $5, $6, $7
                    )
                    RETURNING client_id
                """,
                    cleaned_data['company'],
                    cleaned_data['phone'],
                    cleaned_data['location'],
                    cleaned_data['clientType'],
                    cleaned_data.get('healthScore', 75),
                    'new',
                    cleaned_data.get('status', 'active'),
                )
                client_id = result['client_id']
                logger.info(f"Inserted clients record for client_id {client_id}")

                # Insert primary contact as personnel record
                if cleaned_data.get('primaryContact') or cleaned_data.get('email'):
                    await conn.execute("""
                        INSERT INTO personnel (
                            first_name, last_name, full_name, email, phone,
                            client_id, is_primary, created_at, updated_at
                        ) VALUES (
                            '', '', $1, $2, $3, $4, true, NOW(), NOW()
                        )
                    """,
                        cleaned_data.get('primaryContact', ''),
                        cleaned_data.get('email', ''),
                        cleaned_data.get('phone', ''),
                        client_id,
                    )

                logger.info(f"Successfully imported row {index + 1} with client_id {client_id}")
                inserted_rows += 1

                # Add email to existing set to avoid duplicates within the same file
                if 'email' in cleaned_data:
                    existing_emails.add(cleaned_data['email'].lower())

            except Exception as e:
                failed_rows += 1
                error_msg = f"Failed to import row {index + 1}: {str(e)}"
                logger.error(error_msg)
                warnings.append(error_msg)

        # Calculate processing time
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        logger.info(f"CSV import completed: {inserted_rows} inserted, {failed_rows} failed, {skipped_rows} skipped in {processing_time:.1f}ms")

        return CustomerUploadResponse(
            message=f"Successfully imported {inserted_rows} customers from {file.filename}",
            filename=file.filename,
            total_rows=len(mapped_df),
            inserted_rows=inserted_rows,
            failed_rows=failed_rows,
            skipped_rows=skipped_rows,
            columns_detected=list(mapped_df.columns),
            processing_time_ms=processing_time,
            warnings=warnings if warnings else None
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Customer import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Customer import failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

@router.get("/customer-fields")
async def get_customer_fields():
    """Get available CRM customer fields for mapping."""
    return {
        "success": True,
        "fields": CRM_CUSTOMER_FIELDS,
        "required_fields": ["company", "primaryContact", "email"],
        "optional_fields": [field for field in CRM_CUSTOMER_FIELDS.keys()
                           if field not in ["company", "primaryContact", "email"]]
    }

@router.get("/download-template")
async def download_customer_template():
    """Download a CSV template for customer import."""
    from fastapi.responses import Response

    # Create CSV template with proper column headers
    template_headers = [
        "Company Name",
        "Primary Contact",
        "Email Address",
        "Phone Number",
        "Industry",
        "Location",
        "Status",
        "Client Type",
        "Annual Recurring Revenue",
        "Contract Value",
        "Renewal Date",
        "Health Score",
        "Churn Risk",
        "Satisfaction Score",
        "Expansion Potential"
    ]

    # Sample data rows
    sample_rows = [
        ["Acme Corp", "John Doe", "john@acme.com", "555-1234", "Technology", "San Francisco", "active", "enterprise", "100000", "120000", "2024-12-31", "85", "low", "9.2", "high"],
        ["TechStart Inc", "Jane Smith", "jane@techstart.com", "555-5678", "Healthcare", "New York", "prospect", "startup", "50000", "60000", "2025-06-30", "75", "medium", "8.5", "medium"]
    ]

    # Create CSV content
    csv_content = ",".join(template_headers) + "\n"
    for row in sample_rows:
        csv_content += ",".join(row) + "\n"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customer_import_template.csv"}
    )
