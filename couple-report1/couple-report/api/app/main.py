"""FastAPI 앱 진입점: 컨테이너, CORS, 라우터, 오류 계약 구성."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.container import build_container
from app.routers import auth, chat, couples, health, reports, review, timeline, upload


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.container = build_container(get_settings())
    yield


app = FastAPI(
    title="커플 대화 리포트 API",
    version="0.1.0",
    description="API_SPEC.md 기반 Mock/stub 우선 스캐폴드",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route_module in (auth, couples, upload, timeline, reports, review, chat, health):
    app.include_router(route_module.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "요청 값을 확인해주세요.",
                "detail": exc.errors(),
            }
        },
    )

