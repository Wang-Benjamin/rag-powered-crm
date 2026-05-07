"""
Personnel Router for Lead Generation.
Handles personnel CRUD operations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from service_core.db import get_tenant_connection
from data.repositories import PersonnelRepository

logger = logging.getLogger(__name__)

router = APIRouter()


class PersonnelCreateRequest(BaseModel):
    """Simple request model for creating personnel."""
    first_name: str
    last_name: str
    company_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    linkedin_url: Optional[str] = None
    lead_id: str
    source: str = "api_import"


@router.post("/personnel")
async def create_personnel(
    personnel_data: PersonnelCreateRequest,
    tenant=Depends(get_tenant_connection)
):
    """Create or update a personnel record."""
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")
        personnel_repo = PersonnelRepository()
        data_dict = personnel_data.dict()

        # Try to create personnel
        personnel_id = await personnel_repo.create_personnel(conn, data_dict, user_email)

        if personnel_id:
            return {
                "status": "success",
                "personnel_id": personnel_id,
                "message": "Personnel created successfully",
                "action": "created"
            }
        else:
            raise HTTPException(status_code=422, detail="Failed to create personnel record")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating personnel: {error_msg}")

        # Check if this is a duplicate personnel error - if so, update the existing record
        if "unique_person_company" in error_msg.lower():
            try:
                full_name = f"{personnel_data.first_name} {personnel_data.last_name}".strip()
                result = await personnel_repo.search(conn, full_name=full_name, company_name=personnel_data.company_name, page=1, page_size=1)

                if result.success and result.data and len(result.data) > 0:
                    existing_personnel = result.data[0]
                    personnel_id = existing_personnel.get("personnel_id")

                    # Prepare update data (only non-None fields)
                    update_data = {}
                    if personnel_data.email:
                        update_data["email"] = personnel_data.email
                    if personnel_data.phone:
                        update_data["phone"] = personnel_data.phone
                    if personnel_data.position:
                        update_data["position"] = personnel_data.position
                    if personnel_data.linkedin_url:
                        update_data["linkedin_url"] = personnel_data.linkedin_url

                    # Update the existing personnel
                    if update_data:
                        success = await personnel_repo.update_personnel(conn, personnel_id, update_data, user_email)
                        if success:
                            return {"status": "success", "personnel_id": personnel_id, "message": "Personnel updated successfully", "action": "updated"}
                    else:
                        return {"status": "success", "personnel_id": personnel_id, "message": "Personnel already exists", "action": "exists"}

                raise HTTPException(status_code=422, detail=f"Duplicate personnel: {error_msg}")
            except HTTPException:
                raise
            except Exception as update_error:
                logger.error(f"Error updating personnel: {update_error}")
                raise HTTPException(status_code=422, detail=f"Duplicate personnel: {error_msg}")

        raise HTTPException(status_code=500, detail=str(e))
