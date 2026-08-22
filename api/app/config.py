# 역할: pydantic-settings 설정 — .env.example(SCAFFOLD §4)과 1:1, mock_dir/watsonx_reasoning_effort 포함
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- 모드 ----
    ai_provider: str = "mock"  # mock | watsonx
    app_env: str = "local"
    log_level: str = "INFO"

    # ---- watsonx ----
    watsonx_api_key: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_project_id: str = ""
    watsonx_model_id: str = "openai/gpt-oss-120b"
    watsonx_embedding_model_id: str = "intfloat/multilingual-e5-large"
    watsonx_reasoning_effort: str = "low"
    watsonx_max_tokens: int = 2000

    # ---- 저장소 ----
    postgres_dsn: str = "postgresql://couple:couple@postgres:5432/couple_report"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection_conv: str = "couple_sessions"
    qdrant_collection_knowledge: str = "knowledge"

    # ---- 앱 ----
    jwt_secret: str = "change-me"
    encryption_key: str = ""
    session_gap_min: int = 30
    allowed_origins: str = "http://localhost:5173"
    seed_knowledge_on_start: bool = True

    # ---- 관측성 (Instana) ----
    autowrapt_bootstrap: str = ""
    instana_agent_host: str = ""
    instana_service_name: str = "couple-report-api"

    # ---- 내부 ----
    mock_dir: Path = Path("/app/mock")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
