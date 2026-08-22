# 역할: 업로드→타임라인→리포트→챗봇 1회 스모크 테스트, Mock 모드 통과 기준 (참조: TC-INT-001)
# 사용: docker compose up 후  python scripts/smoke_test.py  (기본 http://localhost:8000)
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):  # Windows cp949 콘솔에서도 ✓/한글 출력
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def call(method: str, path: str, body: dict | None = None, token: str | None = None,
         raw: bytes | None = None, content_type: str | None = None) -> tuple[int, dict | None]:
    url = f"{BASE}{path}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", content_type or "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: text/plain\r\n\r\n".encode() + content + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    print(f"smoke test → {BASE}")
    failed = 0

    # 0. 헬스
    st, body = call("GET", "/health/ready")
    failed += not check("GET /health/ready 200", st == 200, str(body))

    # 1. 가입 → 토큰
    email = f"smoke-{uuid.uuid4().hex[:8]}@smoke-test.dev"  # 예약 도메인(.local 등)은 EmailStr이 거부
    st, body = call("POST", "/api/auth/signup",
                    {"email": email, "password": "password1", "display_name": "스모크"})
    failed += not check("POST /api/auth/signup 201", st == 201 and "token" in (body or {}))
    token = (body or {}).get("token")

    # 2. 커플 연결 흐름 (invite → me)
    st, body = call("POST", "/api/couples/invite", {}, token)
    failed += not check("POST /api/couples/invite 201", st == 201 and "invite_code" in (body or {}))
    st, body = call("GET", "/api/couples/me", token=token)
    failed += not check("GET /api/couples/me 200", st == 200)
    couple_id = (body or {}).get("couple_id") or "00000000-0000-0000-0000-000000000001"

    # 3. 업로드 (fixture) → job
    fixture = ("[카카오톡] 님과 카카오톡 대화\n저장한 날짜 : 2026-08-21\n\n"
               "2026년 8월 17일 월요일\n[김형준] [오후 9:05] 오늘 뭐 했어?\n[윤아♥] [오후 9:07] 공부했지\n").encode("utf-8")
    raw, ctype = multipart({"name_map": json.dumps({"a": "김형준", "b": "윤아♥"}, ensure_ascii=False)},
                           "kakao.txt", fixture)
    st, body = call("POST", f"/api/couples/{couple_id}/upload", token=token, raw=raw, content_type=ctype)
    failed += not check("POST upload 202 + job_id", st == 202 and "job_id" in (body or {}))
    job_id = (body or {}).get("job_id", "")

    st, body = call("GET", f"/api/jobs/{job_id}", token=token)
    failed += not check("GET /api/jobs/{id} 200", st == 200 and (body or {}).get("status") in
                        ("queued", "running", "done"))

    # 4. 타임라인 → 리포트
    st, body = call("GET", f"/api/couples/{couple_id}/timeline", token=token)
    weeks = (body or {}).get("weeks", [])
    failed += not check("GET timeline 200 + weeks", st == 200 and len(weeks) > 0)
    week_start = weeks[-1]["week_start"] if weeks else "2026-08-17"

    st, body = call("GET", f"/api/couples/{couple_id}/reports/{week_start}", token=token)
    ok = st == 200 and (body or {}).get("status") in ("generated", "pending", "insufficient_baseline")
    failed += not check(f"GET reports/{week_start} 200", ok, f"status={(body or {}).get('status')}")
    if (body or {}).get("status") == "generated":
        hl = (body or {}).get("highlights", [])
        failed += not check("리포트 불변 규칙: interpretations >= 2",
                            all(len(h.get("interpretations", [])) >= 2 for h in hl))

    # 5. 챗봇 — fact / advice 리다이렉트
    st, body = call("POST", f"/api/couples/{couple_id}/chat",
                    {"message": "우리 언제 처음 자기야라고 불렀지?"}, token)
    failed += not check("POST chat(fact) 200 + trace_id", st == 200 and "trace_id" in (body or {}))

    st, body = call("POST", f"/api/couples/{couple_id}/chat",
                    {"message": "우리 어떻게 화해해야 할까?"}, token)
    ok = st == 200 and (body or {}).get("intent") == "advice_request" and (body or {}).get("redirect")
    failed += not check("POST chat(advice) → redirect", bool(ok))

    print(f"\n{'PASS' if failed == 0 else f'FAIL ({failed})'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
