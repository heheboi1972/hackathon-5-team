# 커플 대화 리포트

커플이 둘 다 동의한 뒤 카카오톡 대화를 올리면, **판정 없이** 대화 패턴 변화를 주간 리포트로 보여주고 과거 대화를 검색해주는 서비스.
`.txt`와 `.zip` 내보내기 파일을 지원하며, 지표 계산은 **코드**(`metrics.py`)가, 해석·문장은 **LLM**(watsonx)이 담당합니다.
원문 메시지는 PostgreSQL에 Fernet으로 암호화해 저장하고, 리포트·챗봇에 필요한 짧은 인용만 권한 확인 후 복호화합니다.

작업 계획은 [docs/TASKS.md](docs/TASKS.md).

## 빠른 시작

```bash
cp .env.example .env        # Windows: Copy-Item .env.example .env
# .env 에서 AI_PROVIDER=mock 확인, ENCRYPTION_KEY 채우기
#   python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
docker compose up --build
```

- http://localhost:8000/docs — Swagger
- http://localhost:8000/health/ready — `{"postgres":true,"qdrant":true,"watsonx":"mock"}` 이면 성공
- http://localhost:5173 — 프론트 (컨테이너). 로컬 개발은 `cd web && npm install && npm run dev`

테스트:
```bash
# 전체 백엔드 테스트 (uv가 가상환경·의존성을 관리)
cd api && uv run --with-requirements requirements.txt --with pytest python -m pytest tests/ -q

# 업로드→타임라인→리포트→챗봇 스모크 테스트
cd .. && python scripts/smoke_test.py http://localhost:8000
```

자세한 30분 가이드와 트러블슈팅은 [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## 기술 스택

| | |
|---|---|
| 백엔드 | Python 3.12 · FastAPI 0.141 · Uvicorn · Pydantic v2 · psycopg 3 async pool · PyJWT · Passlib/bcrypt · cryptography(Fernet) |
| 프론트엔드 | TypeScript · React 18 · Vite 5 · React Router v6 · TanStack Query v5 · react-hook-form + zod · Recharts · Tailwind/PostCSS 도구 + 프로젝트 전용 CSS |
| 저장소 | PostgreSQL 16(암호화 원문·리포트·작업 큐) · Qdrant 1.19(대화 임베딩) |
| AI | IBM watsonx.ai `openai/gpt-oss-120b`(해석·문장) · `intfloat/multilingual-e5-large`(임베딩) · Mock provider 지원 |
| 실행/배포 | Docker Compose(로컬) · OpenShift Deployment/StatefulSet/Route · Tekton + Buildah · nginx-unprivileged · OpenTelemetry 계측 |

디렉토리 구조와 역할별 편집 범위는 [docs/SCAFFOLD.md](docs/SCAFFOLD.md) §2~3.

## docs/ (읽는 순서)

1. [GETTING_STARTED.md](docs/GETTING_STARTED.md) — 30분 가이드 + 막혔을 때
2. [PRD_기획서_v1.md](docs/PRD_기획서_v1.md) — 기획서
3. [REQUIREMENTS.md](docs/REQUIREMENTS.md) — FR/NFR/US + 추적 매트릭스
4. [API_SPEC.md](docs/API_SPEC.md) — 프론트·백 계약
5. [TRD.md](docs/TRD.md) — 기술 스택 + 아키텍처 + 관측성(OpenTelemetry)
6. [SCAFFOLD.md](docs/SCAFFOLD.md) — 디렉토리 트리, 역할별 편집 범위, .env
7. [TASKS.md](docs/TASKS.md) — 3일 Phase 계획
8. [TEST_CASES.md](docs/TEST_CASES.md) — 완료 기준표
9. [ISSUE.md](docs/ISSUE.md) — **팀 결정 기록**. "이건 왜 이렇게 됐지?" 는 여기 있습니다 (지표 노출 단위, 문장 톤, 제거된 지표, 미결 항목)

## 지켜야 할 것

1. `.env` 커밋 금지 — `.env.example`만
2. LLM이 숫자를 계산하지 않는다 — 지표는 `metrics.py`
3. 리포트·챗봇 문구 금지 — `prompts/banned_patterns.txt` (regex + `tests/test_banned_patterns.py`)
   점수·등급 · 좋다/나쁘다 · "~하세요" · **인물 지목**(A가/○○님이) · **두 사람 비교**(더 자주/~보다) · **수치**(30%)
4. 챗봇은 인용 없으면 답하지 않는다
5. 컴포넌트에서 직접 fetch 금지 — `web/src/api/client.ts` 경유
6. **바꾸기 전에 팀 채널에 말할 것** — 여러 파일이 맞물려 있어 한쪽만 고치면 조용히 어긋납니다
   - 계약 파일 3개: `docs/API_SPEC.md` · `api/app/models/api.py` · `web/src/api/types.ts`
   - 지표는 `{couple, mine}` 만 응답에 담는다 (상대 값 미전송) — 어기면 `tests/test_api_read_paths.py` 가 잡음
   - 라우터는 응답 모델을 직접 만들지 않는다 — `services/projection.py` 의 `build_*` 만 호출
   - `interpretations[]` 는 종결어미 없는 **절** — 프론트가 한 문장으로 합침. **이건 코드가 못 잡으니 제일 조심**

## 현재 주요 흐름

- 회원가입·로그인 → 초대 코드 발급/입력 → 커플 연결 완료
- 연결 완료 화면에서 `.txt` 또는 `.zip` 파일 선택 → 이름 매핑 → 비동기 처리
- 주간 리포트: 요약·지표·발견·제안·기억하고 싶은 순간(메시지 펼쳐보기)
- 돌아보기: 기간별 지표 비교, 세션별 메시지 펼쳐보기, 메모
- 챗봇: 검색된 대화 인용이 있을 때만 답변
