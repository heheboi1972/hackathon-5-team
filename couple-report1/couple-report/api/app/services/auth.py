"""JWT/비밀번호 서비스 자리표시자."""


def issue_mock_token(user_id: str) -> str:
    return f"mock-token-{user_id}"

