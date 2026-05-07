# Prelude CSV Mapping Library

AI-powered CSV column mapping library for the Prelude Platform. Uses deterministic pattern matching combined with AI semantic analysis to map CSV/Excel columns to database schemas.

## Architecture

```
src/
├── __init__.py                  # CSVMapper main interface
├── core/
│   ├── mapping_engine.py       # AI-powered mapping logic
│   ├── file_analyzer.py        # File processing & encoding
│   ├── schema_service.py       # Database schema introspection
│   ├── ai_service.py           # OpenAI/Gemini integration
│   └── mismatch_advisor.py     # Mismatch detection & advice
├── models/
│   ├── mapping_models.py       # Pydantic data models
│   └── mismatch_models.py      # Mismatch-specific models
└── utils/
    ├── confidence_scorer.py     # Mapping confidence calculation
    ├── confidence_constants.py  # Centralized threshold constants
    ├── type_detector.py         # SQL type detection
    └── business_context.py      # Domain-specific patterns
```

## Installation

```bash
cd prelude/prelude-csv
pip install -e .
```

**Dependencies**: pandas, sqlalchemy, psycopg2-binary, pydantic, openai, python-dotenv, openpyxl, charset-normalizer, python-json-logger, typing-extensions

## Quick Start

```python
from csv_mapping import CSVMapper

mapper = CSVMapper(
    database_url="postgresql://user:pass@localhost/db",
    ai_config={"openai_api_key": "sk-..."},
    schema_name="public"
)

result = mapper.analyze_file("sales_data.csv", target_table="sales")

# Progressive disclosure
if result.recommended_flow == "quick_upload":       # ≥90% confidence
    mapped_df = mapper.apply_mappings(result.dataframe, result.mappings)
elif result.recommended_flow == "show_mapping_ui":  # 70-90% confidence
    display_mapping_interface(result)
else:  # require_review, <70% confidence
    display_detailed_review(result)
```

## Configuration

```python
from csv_mapping.models.mapping_models import DatabaseConfig, MappingConfig

db_config = DatabaseConfig(
    connection_string="postgresql://user:pass@host/db",
    schema_name="public",
    service_type="sales"
)

mapping_config = MappingConfig(
    service_context="sales",
    confidence_threshold=0.7,
    use_ai_fallback=True,
    ai_model="gpt-4.1-mini"
)
```

## Core Classes

- **`CSVMapper`**: High-level interface for complete workflows
- **`DynamicMappingEngine`**: AI-powered mapping logic with caching
- **`FileAnalyzer`**: File analysis and encoding detection (static methods)
- **`SchemaService`**: Database schema introspection
- **`MappingRule`**: Column mapping with confidence scoring
- **`AnalysisResult`**: Complete analysis results with recommendations

## Confidence Thresholds

| Action | Threshold | Description |
|--------|-----------|-------------|
| AUTO | ≥90% | Automatic mapping, no review needed |
| REVIEW | 70–90% | Suggest mapping, user confirms |
| MANUAL | <70% | Requires manual column assignment |

## Domain Patterns

- **Sales**: `employee_name` ↔ `salesrep_name`, `total_sales` ↔ `revenue`
- **CRM**: `first_name` ↔ `fname`, `company` ↔ `organization`
- **Employee**: `employee_id` ↔ `emp_id`, `department` ↔ `dept`

## Enhancement Process

1. **Deterministic Matching** — Exact names and common patterns
2. **Confidence Assessment** — Similarity and context scoring
3. **AI Fallback** — Semantic analysis when deterministic matching is insufficient
4. **Action Recommendations** — AUTO, REVIEW, or MANUAL based on thresholds

## Individual Components

```python
from csv_mapping import FileAnalyzer, DynamicMappingEngine, SchemaService

df, metadata = FileAnalyzer.analyze_file("data.csv")
engine = DynamicMappingEngine(config=mapping_config)
mappings = engine.analyze_columns_sync(source_cols, target_cols)
```

## Database Support

```python
mapper = CSVMapper("postgresql://user:pass@host/db")  # PostgreSQL
mapper = CSVMapper("mysql://user:pass@host/db")        # MySQL
mapper = CSVMapper("sqlite:///database.db")            # SQLite
```

## Without AI

```python
mapper = CSVMapper(database_url, ai_config=None)
result = mapper.analyze_file("data.csv")  # Deterministic patterns only
```

## AI Configuration

```bash
export OPENAI_API_KEY="sk-..."   # Primary provider
export GOOGLE_API_KEY="AI..."    # Fallback provider
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

## License

Part of the Prelude Platform. See project licensing terms.
