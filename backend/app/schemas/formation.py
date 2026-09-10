"""Pydantic schemas: FormationRecord (screening / MLRO sign-off / Vistra loop / §V milestones)."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

from app.models.formation import ScreeningStatus, MLROSignoffStatus, VistraStatus


class FormationRecordUpdate(BaseModel):
    # Name / World-Check screening
    screening_status: Optional[ScreeningStatus] = None
    screening_date: Optional[date] = None
    screening_tool: Optional[str] = None
    world_check_reference: Optional[str] = None
    sanctions_hit: Optional[bool] = None
    pep_hit: Optional[bool] = None
    adverse_media_hit: Optional[bool] = None
    screening_findings: Optional[str] = None

    # MLRO sign-off (mlro_signoff_by_id / mlro_signoff_at are stamped server-side)
    mlro_signoff_status: Optional[MLROSignoffStatus] = None
    mlro_signoff_notes: Optional[str] = None

    # Vistra compliance loop
    vistra_status: Optional[VistraStatus] = None
    vistra_submitted_date: Optional[date] = None
    vistra_query_text: Optional[str] = None
    vistra_query_raised_date: Optional[date] = None
    vistra_query_resolved_date: Optional[date] = None
    vistra_approved_date: Optional[date] = None
    vistra_officer: Optional[str] = None

    # §V formation milestones
    kyc_pack_sent_date: Optional[date] = None
    data_input_sheet_sent_date: Optional[date] = None
    first_board_meeting_date: Optional[date] = None
    incorporation_submitted_date: Optional[date] = None
    rod_filed_date: Optional[date] = None
    registers_completed_date: Optional[date] = None
    formation_completed_date: Optional[date] = None


class FormationRecordRead(FormationRecordUpdate):
    id: int
    case_id: int
    screened_by_id: Optional[int] = None
    mlro_signoff_by_id: Optional[int] = None
    mlro_signoff_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
