"""JSON 파싱 공용 유틸리티."""

import json
from typing import Any


def parse_json(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("JSON object가 필요합니다.")
    return parsed

