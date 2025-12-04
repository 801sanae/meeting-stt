from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.config.settings import get_settings


settings = get_settings()


async def summarize_meeting(transcript: str) -> str:
    """Azure OpenAI Chat Completions를 사용해 회의 요약을 생성."""

    # STT 결과가 비어 있으면 굳이 요약 호출을 하지 않고 고정 메시지 반환
    if not transcript or not transcript.strip():
        return "인식된 발화가 없어 요약할 내용이 없습니다."

    if not (
        settings.azure_openai_endpoint
        and settings.azure_openai_api_key
        and settings.azure_openai_deployment_summary
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI 요약 설정이 올바르지 않습니다.",
        )

    endpoint = settings.azure_openai_endpoint.rstrip("/")
    deployment = settings.azure_openai_deployment_summary
    api_version = settings.azure_openai_api_version

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    headers = {
        "api-key": settings.azure_openai_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    system_prompt = (
        "당신은 회의록을 요약하는 비서입니다. "
        "입력으로 한국어 회의 전체 발언이 주어지면, 아래 형식으로 간결하게 요약하세요.\n\n"
        "- 회의 개요 (한두 문장)\n"
        "- 주요 결정 사항 (bullet)\n"
        "- TODO / Action items (담당자/마감일이 있으면 포함)\n"
    )

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 800,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure OpenAI 요약 호출 실패: {resp.status_code} {resp.text}",
        )

    data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure OpenAI 요약 응답에서 내용을 찾을 수 없습니다.",
        )

    return content.strip()
