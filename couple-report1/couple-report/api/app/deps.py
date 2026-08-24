"""라우터 공용 의존성. 인증 저장소 구현 전에는 Mock 멤버를 반환한다."""

from typing import Annotated, Literal

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=True)


def current_member(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> Literal["a", "b"]:
    # TODO(FR-000): JWT 검증 후 DB의 실제 couple member를 반환한다.
    if credentials.credentials.endswith("-b"):
        return "b"
    return "a"


CurrentMember = Annotated[Literal["a", "b"], Depends(current_member)]
