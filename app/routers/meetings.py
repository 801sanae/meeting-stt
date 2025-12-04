from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status, HTTPException

from app.models.meeting import (
    MeetingDetailResponse,
    MeetingListItem,
    MeetingRecordResponse,
)
from app.service.meeting_service import MeetingService, get_meeting_service_dep


router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/record", response_model=MeetingRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_meeting(
    audio: UploadFile = File(...),
    duration_seconds: float = Form(...),
    service: MeetingService = Depends(get_meeting_service_dep),
) -> MeetingRecordResponse:
    audio_bytes = await audio.read()

    # STT + 요약 + 저장까지는 서비스 계층에서 처리
    return await service.record_meeting(audio_bytes=audio_bytes, duration_seconds=duration_seconds)


@router.get("/", response_model=list[MeetingListItem])
def list_meetings(
    skip: int = 0,
    limit: int = 20,
    service: MeetingService = Depends(get_meeting_service_dep),
) -> list[MeetingListItem]:
    return service.list_meetings(skip=skip, limit=limit)


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def get_meeting(
    meeting_id: UUID,
    service: MeetingService = Depends(get_meeting_service_dep),
) -> MeetingDetailResponse:
    return service.get_meeting(meeting_id=meeting_id)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: UUID,
    service: MeetingService = Depends(get_meeting_service_dep),
) -> None:
    service.delete_meeting(meeting_id=meeting_id)

    return None
