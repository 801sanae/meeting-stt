from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.models.meeting import (
    MeetingDetailResponse,
    MeetingListItem,
    MeetingRecordResponse,
)
from app.repository.meeting_respository import (
    create_meeting as repo_create_meeting,
    list_meetings as repo_list_meetings,
    get_meeting as repo_get_meeting,
    delete_meeting as repo_delete_meeting,
)
from app.service.stt_service import transcribe
from app.service.summary_service import summarize_meeting


EMPTY_TRANSCRIPT_MESSAGE = "인식된 발화가 없습니다."


def create_meeting(
    db: Session,
    *,
    transcript: str,
    summary: str,
) -> MeetingRecordResponse:
    display_transcript = transcript.strip() if isinstance(transcript, str) else transcript
    if not display_transcript:
        display_transcript = EMPTY_TRANSCRIPT_MESSAGE

    meeting = repo_create_meeting(
        db,
        full_transcript=display_transcript,
        summary=summary,
    )

    return MeetingRecordResponse(
        id=meeting.id,
        transcript=meeting.full_transcript,
        summary=meeting.summary,
    )


def list_meetings_service(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 20,
) -> List[MeetingListItem]:
    meetings = repo_list_meetings(db, skip=skip, limit=limit)

    return [
        MeetingListItem(
            id=m.id,
            title=m.title,
            summary=m.summary,
            created_at=m.created_at,
        )
        for m in meetings
    ]


def get_meeting_service(
    db: Session,
    *,
    meeting_id: UUID,
) -> MeetingDetailResponse:
    meeting = repo_get_meeting(db, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    return MeetingDetailResponse(
        id=meeting.id,
        title=meeting.title,
        full_transcript=meeting.full_transcript,
        summary=meeting.summary,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


def delete_meeting_service(
    db: Session,
    *,
    meeting_id: UUID,
) -> None:
    deleted = repo_delete_meeting(db, meeting_id=meeting_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")


class MeetingService:
    def __init__(self, db: Session) -> None:
        self._db = db

    async def record_meeting(self, *, audio_bytes: bytes, duration_seconds: float) -> MeetingRecordResponse:
        """STT + 요약 + 회의 저장까지 한 번에 처리하는 고수준 유즈케이스."""

        transcript = await transcribe(
            audio_bytes=audio_bytes,
            db=self._db,
            duration_seconds=duration_seconds,
        )

        summary = await summarize_meeting(transcript)

        return create_meeting(self._db, transcript=transcript, summary=summary)

    def list_meetings(self, *, skip: int = 0, limit: int = 20) -> List[MeetingListItem]:
        return list_meetings_service(self._db, skip=skip, limit=limit)

    def get_meeting(self, *, meeting_id: UUID) -> MeetingDetailResponse:
        return get_meeting_service(self._db, meeting_id=meeting_id)

    def delete_meeting(self, *, meeting_id: UUID) -> None:
        delete_meeting_service(self._db, meeting_id=meeting_id)


def get_meeting_service_dep(db: Session = Depends(get_db)) -> MeetingService:
    """FastAPI DI용 MeetingService provider."""

    return MeetingService(db)