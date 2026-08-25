# 역할: 내부 툴 공통 — OTel 스팬 tracer (참조: API_SPEC §8, TRD §9.1)
# Instana agent 는 쓰지 않지만(ISSUE D3) OTel API 는 남겨둔다 — execution_trace 와 함께
# "어느 툴이 몇 번 불렸나"를 보는 지점이라, agent 가 붙는 환경에서는 그대로 수집된다.
# ai_service.py 와 같은 no-op 폴백 패턴.
from __future__ import annotations

try:  # OTel 은 선택. 없으면 no-op
    from opentelemetry import trace as _otel

    tracer = _otel.get_tracer("couple-report")
except Exception:  # pragma: no cover

    class _NoopSpan:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_attribute(self, *a, **k): pass

    class _NoopTracer:
        def start_as_current_span(self, *a, **k): return _NoopSpan()

    tracer = _NoopTracer()
