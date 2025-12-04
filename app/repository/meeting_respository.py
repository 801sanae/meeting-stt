from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Meeting


def create_meeting(
    db: Session,
    *,
    full_transcript: str,
    summary: str,
) -> Meeting:
    """회의 레코드를 생성하고 커밋한 뒤, 생성된 Meeting 객체를 반환한다."""

    meeting = Meeting(
        title=None,
        started_at=None,
        ended_at=None,
        full_transcript=full_transcript,
        summary=summary,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def list_meetings(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 20,
) -> List[Meeting]:
    """최근 생성된 순으로 회의 목록을 조회한다."""

    return (
        db.query(Meeting)
        .order_by(Meeting.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_meeting(
    db: Session,
    *,
    meeting_id: UUID,
) -> Optional[Meeting]:
    """ID로 단일 회의를 조회한다. 없으면 None 반환."""

    return db.query(Meeting).filter(Meeting.id == meeting_id).first()


def delete_meeting(
    db: Session,
    *,
    meeting_id: UUID,
) -> bool:
    """ID로 회의를 삭제하고, 삭제 여부를 bool로 반환한다."""

    meeting = get_meeting(db, meeting_id=meeting_id)
    if meeting is None:
        return False

    db.delete(meeting)
    db.commit()
    return True