from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import asyncio

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
import httpx

from app.config.settings import get_settings
from app.models.models import SttUsage


class SttBackend(str, Enum):
    AZURE_SPEECH = "azure_speech"
    WHISPER = "whisper"


settings = get_settings()


def _current_month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    if now is None:
        now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def get_azure_speech_usage_hours(db: Session, now: datetime | None = None) -> float:
    start, end = _current_month_range(now)
    total_seconds: float = (
        db.query(func.coalesce(func.sum(SttUsage.duration_seconds), 0.0))
        .filter(
            SttUsage.provider == SttBackend.AZURE_SPEECH.value,
            SttUsage.occurred_at >= start,
            SttUsage.occurred_at < end,
        )
        .scalar()
    )
    return total_seconds / 3600.0


def register_azure_speech_usage(db: Session, duration_seconds: float) -> None:
    usage = SttUsage(provider=SttBackend.AZURE_SPEECH.value, duration_seconds=duration_seconds)
    db.add(usage)
    db.commit()


def choose_backend() -> SttBackend:
    """Flag 기반으로 STT 백엔드를 선택.

    우선순위:
    - use_speech_service=True 이면 Azure Speech
    - 아니면 Whisper
    """

    if settings.use_speech_service:
        return SttBackend.AZURE_SPEECH
    return SttBackend.WHISPER


def ensure_can_use_azure_speech(db: Session, next_duration_seconds: float) -> None:
    """월 5시간(기본값) 무료 쿼터를 넘기지 않도록 검사.

    flag가 켜져 있고, 현재 사용량 + 이번 요청 길이가
    설정된 무료 시간(stt_free_quota_hours_per_month)을 넘으면 예외 발생.
    """

    allowed_hours = settings.stt_free_quota_hours_per_month
    used_hours = get_azure_speech_usage_hours(db)
    next_hours = next_duration_seconds / 3600.0

    if used_hours + next_hours > allowed_hours:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Azure Speech STT 무료 사용량을 초과하여 사용할 수 없습니다.",
        )


# 아래 두 함수는 실제 Azure Speech / Whisper API 연동 시 사용될 자리입니다.
# 현재는 인터페이스만 정의하고, 구체 구현은 이후 단계에서 추가합니다.

async def transcribe_with_azure_speech(audio_bytes: bytes) -> str:
    """Azure Speech Service REST API로 음성을 텍스트로 변환.

    참고: https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text
    """

    if not (settings.azure_speech_key and settings.azure_speech_region):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Azure Speech 설정이 올바르지 않습니다.",
        )

    region = settings.azure_speech_region
    language = settings.azure_speech_language

    url = (
        f"https://{region}.stt.speech.microsoft.com/"
        "speech/recognition/conversation/cognitiveservices/v1"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        # 프런트엔드에서 업로드하는 WAV(PCM) 포맷에 맞춰 Content-Type 설정
        "Content-Type": "audio/wav",
        "Accept": "application/json",
    }

    params = {"language": language}

    # 일시적인 네트워크 끊김(ReadError 등)을 완화하기 위해 간단한 재시도 로직 적용
    max_retries = 3
    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_retries + 1):
            try:
                resp = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    content=audio_bytes,
                )
                break
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= max_retries:
                    # 네트워크 계층 오류 (ReadError 등)를 502로 변환
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Azure Speech STT 네트워크 오류(재시도 {max_retries}회 실패): {exc}",
                    ) from exc
                # 간단한 선형 백오프 (1초, 2초, ...)
                await asyncio.sleep(attempt)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure Speech STT 호출 실패: {resp.status_code} {resp.text}",
        )

    data = resp.json()

    # 대표적인 응답 형태: {"RecognitionStatus": "Success", "DisplayText": "..."}
    text = data.get("DisplayText") if isinstance(data, dict) else None
    if text is None and isinstance(data, dict):
        # 일부 응답에서는 NBest[0].Display 가 있을 수 있음
        nbest = data.get("NBest")
        if isinstance(nbest, list) and nbest:
            text = nbest[0].get("Display") or nbest[0].get("Lexical")

    # 빈 문자열이 반환될 때는 디버깅을 위해 원본 응답 일부를 로그로 출력
    if text == "":
        print("[STT] Azure Speech returned empty text. raw:", resp.text[:500])

    # text가 None 인 경우에만 에러로 간주. ""(빈 문자열)은 "인식된 발화 없음"으로 처리.
    if text is None:
        # 디버깅을 위해 원본 응답의 일부를 함께 노출 (길이 제한)
        raw = resp.text
        if len(raw) > 500:
            raw = raw[:500] + "... (truncated)"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure Speech STT 응답에서 텍스트를 찾을 수 없습니다. raw={raw}",
        )

    return text


async def transcribe_with_whisper(audio_bytes: bytes) -> str:
    """외부 Whisper API(예: Simplismart)를 사용해 음성을 텍스트로 변환."""

    if not (settings.whisper_api_base_url and settings.whisper_api_key):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Whisper API 설정이 올바르지 않습니다.",
        )

    base_url = settings.whisper_api_base_url.rstrip("/")
    url = f"{base_url}/transcribe"

    headers = {
        "Authorization": f"Bearer {settings.whisper_api_key}",
        "Content-Type": "audio/wav",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, content=audio_bytes)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Whisper API 호출 실패: {resp.status_code} {resp.text}",
        )

    data = resp.json()
    text = data.get("text") or data.get("transcript")

    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Whisper API 응답에서 텍스트를 찾을 수 없습니다.",
        )

    return text


async def transcribe(audio_bytes: bytes, db: Session, duration_seconds: float) -> str:
    """플래그와 Azure Speech 무료 쿼터에 따라 STT 백엔드를 선택하고 호출.

    동작 규칙:
    - settings.use_speech_service 가 True 이고 키/리전이 설정되어 있으면 Azure Speech를 우선 사용
      - 이번 요청 길이(duration_seconds)를 포함해 월 무료 시간(stt_free_quota_hours_per_month)을 넘기면 429 에러
    - 그렇지 않고 settings.use_whisper_api 가 True 이고 설정이 있으면 Whisper API 사용
    - 둘 다 아니면 503 에러
    """

    # 1) Azure Speech Service 우선 사용 (flag + 키/리전 필요)
    if (
        settings.use_speech_service
        and settings.azure_speech_key
        and settings.azure_speech_region
    ):
        ensure_can_use_azure_speech(db, duration_seconds)
        text = await transcribe_with_azure_speech(audio_bytes)
        register_azure_speech_usage(db, duration_seconds)
        return text

    # 2) Whisper API (예: Simplismart). 기본값은 use_whisper_api=False 이므로 명시적으로 켜야 함.
    if (
        settings.use_whisper_api
        and settings.whisper_api_base_url
        and settings.whisper_api_key
    ):
        return await transcribe_with_whisper(audio_bytes)

    # 3) 어떤 백엔드도 사용 불가한 경우
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="사용 가능한 STT 백엔드가 설정되어 있지 않습니다.",
    )
