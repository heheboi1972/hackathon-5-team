# 역할: 라우터 공용 의존성 (참조: API_SPEC 공통 규칙)
# 스캐폴딩: auth(TASKS 2-1) 전까지 요청자를 A 로 고정. 붙일 때 이 파일만 고치면 라우터는 그대로.
from __future__ import annotations

from .models.api import Who

MOCK_ME: Who = "a"


def current_member() -> Who:
    """요청자가 이 커플에서 a 인지 b 인지.

    `mine`(지표)·`sentiment`(내 단어) 를 요청자 것으로 채우는 데 쓴다 (P-3 예외, ISSUE B1·B3).
    TODO(윤석): JWT → users → couples(user_a/user_b) 조회로 교체 (TASKS 2-1).
    테스트는 app.dependency_overrides[current_member] 로 갈아끼운다.
    """
    return MOCK_ME
