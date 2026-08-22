# 역할: FastAPI 엔트리포인트 — lifespan에서 container 생성, 라우터 등록, CORS (참조: TRD, SCAFFOLD §2)
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .container import build_container
from .routers import auth, chat, couples, health, reports, review, timeline, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app.state.container = await build_container(settings)
    logging.getLogger(__name__).info(
        "기동: provider=%s postgres=%s qdrant=%s",
        app.state.container.ai.provider_name,
        app.state.container.postgres_up,
        app.state.container.qdrant_up,
    )
    yield
    await app.state.container.close()


app = FastAPI(title="커플 대화 리포트 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def error_shape_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """API_SPEC 공통 에러 형식 { "error": { code, message, detail? } } 로 변환."""
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        body = {"error": exc.detail}
    else:
        body = {"error": {"code": "ERROR", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


for r in (auth, couples, upload, timeline, reports, review, chat, health):
    app.include_router(r.router)
