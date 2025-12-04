from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MeetingRecordResponse(BaseModel):
    id: UUID
    transcript: str | None
    summary: str | None = None


class MeetingListItem(BaseModel):
    id: UUID
    title: str | None
    summary: str | None
    created_at: datetime


class MeetingDetailResponse(BaseModel):
    id: UUID
    title: str | None
    full_transcript: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime