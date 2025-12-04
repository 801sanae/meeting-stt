from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.settings import get_settings
from app.models.models import SttUsage
from app.service.stt_service import get_azure_speech_usage_hours, SttBackend


router = APIRouter(prefix="/admin/stt", tags=["admin-stt"])


@router.get("/usage")
def get_stt_usage(db: Session = Depends(get_db)) -> dict:
    """현재 월 기준 Azure Speech STT 사용량/쿼터/잔여 시간 조회."""

    settings = get_settings()
    used_hours = get_azure_speech_usage_hours(db)
    quota_hours = settings.stt_free_quota_hours_per_month
    remaining = max(quota_hours - used_hours, 0.0)

    now_utc = datetime.now(timezone.utc)

    return {
        "provider": SttBackend.AZURE_SPEECH.value,
        "used_hours_this_month": used_hours,
        "quota_hours_per_month": quota_hours,
        "remaining_hours": remaining,
        "now_utc": now_utc.isoformat(),
    }


@router.get("/usage/history")
def get_stt_usage_history(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """최근 STT 사용 이력을 조회 (디버깅/모니터링용)."""

    q = (
        db.query(SttUsage)
        .filter(SttUsage.provider == SttBackend.AZURE_SPEECH.value)
        .order_by(SttUsage.occurred_at.desc())
        .limit(limit)
    )

    results: list[dict] = []
    for row in q.all():
        results.append(
            {
                "id": str(row.id),
                "provider": row.provider,
                "duration_seconds": float(row.duration_seconds),
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            }
        )

    return results
