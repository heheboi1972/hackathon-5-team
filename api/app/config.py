# 역할: pydantic-settings 설정 — .env.example(SCAFFOLD §4)과 1:1, mock_dir/watsonx_reasoning_effort 포함
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 는 실행 위치와 무관하게 저장소 루트에서 찾는다.
# 상대경로 ".env" 만 두면 `cd api && uvicorn app.main:app` 처럼 띄웠을 때 파일을 못 찾고,
# pydantic-settings 는 에러 없이 기본값(빈 문자열)으로 떨어져 키가 조용히 사라진다.
# 컨테이너에는 이 경로에 파일이 없지만 docker-compose 가 실제 환경변수로 주입하고,
# 존재하지 않는 env_file 은 무시되므로 문제되지 않는다.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # 뒤쪽이 우선 — 저장소 루트를 기본으로 두되, 실행 디렉터리의 .env 가 있으면 그것을 덮어쓴다
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    # ---- 앱 ----
    jwt_secret: str = "change-me"
    encryption_key: str = ""
    session_gap_min: int = 30
    allowed_origins: str = "http://localhost:5173"
    knowledge_dir: str = "data/knowledge"        # 지식 문서·템플릿·감성 시드 (메모리 로드)

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
