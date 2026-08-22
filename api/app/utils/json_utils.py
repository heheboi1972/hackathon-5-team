# 역할: JSON 유틸 — 코드펜스 제거 파싱(LLM 출력용) + mock/*.json 로더
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)

# 로컬(api/mock)·컨테이너(/app/mock) 어디서든 같은 상대 위치
MOCK_DIR = Path(__file__).resolve().parents[2] / "mock"


def strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip())


def loads_relaxed(text: str) -> Any:
    """LLM 출력에서 흔한 코드펜스를 벗겨내고 JSON 파싱."""
    return json.loads(strip_fences(text))


def load_mock(name: str) -> dict[str, Any]:
    """api/mock/<name>.json 로드 (Mock 모드 고정 응답)."""
    return json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))
