from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://meeting:meeting@localhost:55432/meeting_stt"

    # Azure OpenAI (Whisper, summary 등)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment_stt: str | None = None
    azure_openai_deployment_summary: str | None = None
    azure_openai_api_version: str = "2024-05-01-preview"

    # Azure Speech Service
    azure_speech_endpoint: str | None = None
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None
    azure_speech_language: str = "ko-KR"

    # 외부 Whisper API (예: Simplismart)
    whisper_api_base_url: str | None = None
    whisper_api_key: str | None = None

    # STT 사용 전략
    use_speech_service: bool = True
    use_whisper_api: bool = False

    # Azure Speech 무료 쿼터 (시간)
    stt_free_quota_hours_per_month: float = 5.0

    # Observability
    enable_metrics: bool = True
    loki_url: str | None = None
    loki_auth_username: str | None = None
    loki_auth_password: str | None = None
    app_name: str = "meeting-stt"
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
