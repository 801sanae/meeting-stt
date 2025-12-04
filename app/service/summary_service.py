from __future__ import annotations

from fastapi import HTTPException, status
from langchain.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from pathlib import Path

from app.config.settings import get_settings


settings = get_settings()


def _build_llm() -> AzureChatOpenAI:
  """LangChain AzureChatOpenAI 인스턴스를 생성한다.

  설정이 올바르지 않으면 HTTP 예외를 발생시켜 상위 레이어에서 핸들링하도록 한다.
  """

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

  return AzureChatOpenAI(
      azure_endpoint=endpoint,
      api_key=settings.azure_openai_api_key,
      azure_deployment=settings.azure_openai_deployment_summary,
      openai_api_version=settings.azure_openai_api_version,
      temperature=0.2,
  )


_llm: AzureChatOpenAI | None = None
_system_prompt_cache: str | None = None
_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompt" / "summary_system_prompt.txt"


def _get_llm() -> AzureChatOpenAI:
  global _llm
  if _llm is None:
      _llm = _build_llm()
  return _llm


def _get_system_prompt() -> str:
  global _system_prompt_cache
  if _system_prompt_cache is not None:
      return _system_prompt_cache

  default_prompt = (
      "당신은 회의록을 요약하는 비서입니다. "
      "입력으로 한국어 회의 전체 발언이 주어지면, 아래 형식으로 간결하게 요약하세요.\n\n"
      "- 회의 개요 (한두 문장)\n"
      "- 주요 결정 사항 (bullet)\n"
      "- TODO / Action items (담당자/마감일이 있으면 포함)\n"
  )

  try:
      text = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
      _system_prompt_cache = text or default_prompt
  except OSError:
      _system_prompt_cache = default_prompt

  return _system_prompt_cache


async def summarize_meeting(transcript: str) -> str:
  """LangChain + PromptTemplate 를 사용해 회의 요약을 생성."""

  # STT 결과가 비어 있으면 굳이 요약 호출을 하지 않고 고정 메시지 반환
  if not transcript or not transcript.strip():
      return "인식된 발화가 없어 요약할 내용이 없습니다."

  llm = _get_llm()

  system_prompt = _get_system_prompt()

  prompt = ChatPromptTemplate.from_messages(
      [
          ("system", system_prompt),
          ("user", "{transcript}"),
      ]
  )

  chain = prompt | llm

  try:
      result = await chain.ainvoke({"transcript": transcript})
  except Exception as exc:  # LangChain 내부 예외를 HTTPException 으로 래핑
      raise HTTPException(
          status_code=status.HTTP_502_BAD_GATEWAY,
          detail=f"Azure OpenAI 요약 호출 실패: {exc}",
      ) from exc

  # result 는 AIMessage 이므로 content 에 최종 텍스트가 들어 있음
  content = getattr(result, "content", None)
  if not isinstance(content, str) or not content.strip():
      raise HTTPException(
          status_code=status.HTTP_502_BAD_GATEWAY,
          detail="Azure OpenAI 요약 응답에서 내용을 찾을 수 없습니다.",
      )

  return content.strip()
