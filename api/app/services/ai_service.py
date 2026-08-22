"""
AI 서비스 — watsonx.ai 호출의 유일한 진입점. (교육 자료 rag_common.py / _common.py 의 검증된 패턴 이식)

  - 임베딩: e5 계열은 passage: / query: 접두사 필수
  - 생성  : gpt-oss 는 추론 모델이라 reasoning_effort="low" + 토큰 부족 시 1회 증액 재시도
  - Mock  : AI_PROVIDER=mock 이면 외부 호출 없이 결정적 응답 (데모 백업·프론트 개발용)

사용:
    ai = build_ai_service(settings)
    vec  = await ai.embed_query("우리 언제 제주도 얘기했지?")
    vecs = await ai.embed_documents(["A: 뭐해?\\nB: 공부"])
    text = await ai.generate(messages=[{"role":"system","content":...},{"role":"user","content":...}])
    obj  = await ai.generate_json(messages, mock_key="select")   # JSON 강제 + 펜스 제거
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

try:  # OTel 은 선택. 없으면 no-op
    from opentelemetry import trace as _otel
    _tracer = _otel.get_tracer("couple-report")
except Exception:  # pragma: no cover
    _otel = None

    class _NoopSpan:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_attribute(self, *a, **k): pass

    class _NoopTracer:
        def start_as_current_span(self, *a, **k): return _NoopSpan()

    _tracer = _NoopTracer()


class AIServiceError(RuntimeError):
    pass


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


def strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip())


# ---------------------------------------------------------------- 인터페이스


class AIService(ABC):
    provider_name: str
    vector_size: int

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 2000) -> str: ...

    async def generate_json(
        self, messages: list[dict[str, str]], max_tokens: int = 2000, mock_key: str | None = None
    ) -> dict[str, Any]:
        raw = await self.generate(messages, max_tokens=max_tokens, **({"mock_key": mock_key} if mock_key else {}))
        try:
            return json.loads(strip_fences(raw))
        except json.JSONDecodeError as e:
            raise AIServiceError(f"JSON 파싱 실패: {e}: {raw[:200]}") from e

    async def close(self) -> None:
        return None


# ---------------------------------------------------------------- Mock


class MockAIService(AIService):
    """외부 모델 없이 전 흐름을 검증. 임베딩은 문자 n-gram 해시, 생성은 mock/<key>.json."""

    provider_name = "mock"
    vector_size = 384

    def __init__(self, mock_dir: Path):
        self.mock_dir = mock_dir

    async def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    async def embed_query(self, text):
        return self._embed(text)

    async def generate(self, messages, max_tokens=2000, mock_key: str | None = None):
        key = mock_key or self._infer_key(messages)
        path = self.mock_dir / f"{key}.json"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return json.dumps({"mock": True, "key": key, "note": f"mock/{key}.json 없음"}, ensure_ascii=False)

    @staticmethod
    def _infer_key(messages) -> str:
        system = messages[0].get("content", "") if messages else ""
        m = re.search(r"TASK:(\w+)", system)
        return m.group(1).lower() if m else "default"

    def _embed(self, text: str) -> list[float]:
        t = re.sub(r"\s+", " ", text.strip().lower())
        vec = [0.0] * self.vector_size
        for i in range(len(t) - 2):
            h = int(hashlib.md5(t[i:i + 3].encode()).hexdigest(), 16)
            vec[h % self.vector_size] += 1.0
        n = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / n for v in vec]


# ---------------------------------------------------------------- watsonx


class WatsonxAIService(AIService):
    provider_name = "watsonx"

    def __init__(self, api_key: str, url: str, project_id: str, model_id: str, embedding_model_id: str,
                 reasoning_effort: str = "low", temperature: float = 0.0):
        from ibm_watsonx_ai import Credentials
        from ibm_watsonx_ai.foundation_models import Embeddings, ModelInference
        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as E

        creds = Credentials(url=url, api_key=api_key)
        self.model_id = model_id
        self.embedding_model_id = embedding_model_id
        self.reasoning_effort = reasoning_effort
        self.temperature = temperature
        self._model = ModelInference(model_id=model_id, credentials=creds, project_id=project_id)
        self._emb = Embeddings(
            model_id=embedding_model_id, credentials=creds, project_id=project_id,
            params={E.TRUNCATE_INPUT_TOKENS: 512, E.RETURN_OPTIONS: {"input_text": False}},
        )
        self.vector_size = 1024 if "e5-large" in embedding_model_id else 768

    # --- 임베딩 (e5 접두사) ---
    @property
    def _is_e5(self) -> bool:
        return "e5" in self.embedding_model_id.lower()

    async def embed_documents(self, texts):
        if self._is_e5:
            texts = [f"passage: {t}" for t in texts]
        with _tracer.start_as_current_span("watsonx.embed") as s:
            s.set_attribute("model", self.embedding_model_id); s.set_attribute("n", len(texts))
            return await asyncio.to_thread(self._emb.embed_documents, texts)

    async def embed_query(self, text):
        if self._is_e5:
            text = f"query: {text}"
        with _tracer.start_as_current_span("watsonx.embed_query") as s:
            s.set_attribute("model", self.embedding_model_id)
            return await asyncio.to_thread(self._emb.embed_query, text)

    # --- 생성 (gpt-oss 토큰 예산) ---
    async def generate(self, messages, max_tokens=2000, mock_key=None):
        extra = {"reasoning_effort": self.reasoning_effort} if "gpt-oss" in self.model_id else {}
        with _tracer.start_as_current_span("watsonx.generate") as s:
            s.set_attribute("model", self.model_id)
            s.set_attribute("input_chars", sum(len(m.get("content", "")) for m in messages))
            last = None
            for budget in (max_tokens, max_tokens + 2000):   # 추론에 토큰을 다 쓰면 본문이 비므로 1회 증액
                resp = await asyncio.to_thread(
                    self._model.chat, messages=messages,
                    params={"temperature": self.temperature, "max_tokens": budget, **extra},
                )
                msg = resp["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                s.set_attribute("attempt_budget", budget)
                if content:
                    s.set_attribute("output_chars", len(content))
                    return content
                last = resp
                if not msg.get("reasoning_content"):
                    break
            fr = last["choices"][0].get("finish_reason") if last else None
            raise AIServiceError(f"모델({self.model_id})이 본문 없이 응답을 마침 (finish_reason={fr})")


# ---------------------------------------------------------------- 팩토리


def build_ai_service(settings) -> AIService:
    if settings.ai_provider == "mock":
        return MockAIService(Path(settings.mock_dir))
    return WatsonxAIService(
        api_key=settings.watsonx_api_key, url=settings.watsonx_url, project_id=settings.watsonx_project_id,
        model_id=settings.watsonx_model_id, embedding_model_id=settings.watsonx_embedding_model_id,
        reasoning_effort=settings.watsonx_reasoning_effort,
    )
