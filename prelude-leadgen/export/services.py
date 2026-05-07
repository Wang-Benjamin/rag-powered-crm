"""
Export Services for Lead Generation

Handles data export in various formats (CSV, JSON, etc.)
"""

import json
import logging
import pandas as pd
import io
from typing import Dict, Any, List
from data.repositories import LeadRepository
from service_core.db import get_current_conn

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting lead data in various formats."""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id or "system"
        self.lead_repository = LeadRepository()
    
    async def export_leads(self, format: str = "csv", filters: Dict[str, Any] = None) -> str:
        """Export leads to specified format"""
        try:
            conn = get_current_conn()
            # Get leads based on filters using repository
            leads = await self.lead_repository.get_leads(
                conn,
                skip=0,
                limit=1000,  # Export up to 1000 leads
                **filters if filters else {}
            )
            
            if format.lower() == "csv":
                # Export to CSV
                df = pd.DataFrame(leads)
                output = io.StringIO()
                df.to_csv(output, index=False)
                return output.getvalue()
            
            elif format.lower() == "json":
                # Export to JSON
                return json.dumps(leads, indent=2)
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting leads: {e}")
            raise


def get_export_service(user_id: str = None) -> ExportService:
    """Get export service instance"""
    return ExportService(user_id)