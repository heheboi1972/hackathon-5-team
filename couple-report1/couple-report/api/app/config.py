"""환경 변수 기반 애플리케이션 설정. SCAFFOLD.md §4."""

from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # 최소 로컬 검증용; 컨테이너에는 requirements로 설치된다.
    from pydantic import BaseModel as BaseSettings
    from pydantic import ConfigDict as SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    ai_provider: str = "mock"
    app_env: str = "local"
    log_level: str = "INFO"

    watsonx_api_key: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_project_id: str = ""
    watsonx_model_id: str = "openai/gpt-oss-120b"
    watsonx_embedding_model_id: str = "intfloat/multilingual-e5-large"
    watsonx_reasoning_effort: str = "low"
    watsonx_max_tokens: int = 2000

    postgres_dsn: str = "postgresql://couple:couple@postgres:5432/couple_report"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection_conv: str = "couple_sessions"

    jwt_secret: str = "change-me"
    encryption_key: str = ""
    session_gap_min: int = 30
    allowed_origins: str = "http://localhost:5173"
    knowledge_dir: Path = Path("data/knowledge")
    mock_dir: Path = Path("/app/mock")

    autowrapt_bootstrap: str = ""
    instana_agent_host: str = ""
    instana_service_name: str = "couple-report-api"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
