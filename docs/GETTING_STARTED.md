# 처음 시작하는 사람을 위한 가이드 (GETTING_STARTED.md)

> 목표: 클론부터 첫 업로드까지 **30분**. 막히면 §6, 명세서 읽는 법은 §8.

## 0. 이 프로젝트가 뭔지 3줄

- 커플이 둘 다 동의한 뒤 카톡 대화를 올리면, **판정 없이** 대화 패턴 변화를 주간 리포트로 보여주고 과거 대화를 검색해주는 서비스
- 지표 계산은 **코드**가, 해석·문장은 **LLM**이. 이 경계를 넘지 않는 게 제일 중요한 규칙
- 자세한 건 `docs/PRD_기획서_v1.md` §0~2. 10분이면 읽어요

## 1. 준비물

| 것 | 확인 명령 | 없으면 |
|---|---|---|
| Git | `git --version` | git-scm.com |
| Docker Desktop | `docker compose version` | docker.com. Windows는 WSL2 백엔드 켜기 |
| Node 20+ (프론트 할 사람만) | `node -v` | nodejs.org |
| Python 3.11 (백엔드 로컬 실행할 사람만) | `python --version` | 컨테이너로만 돌리면 불필요 |
| VS Code + Claude Code | — | — |

## 2. 처음 한 번 (10분)

```bash
git clone <repo-url> couple-report
cd couple-report
cp .env.example .env          # Windows: Copy-Item .env.example .env
```

`.env`를 열어서 **일단 이것만** 확인:
```
AI_PROVIDER=mock
```
Mock 모드면 watsonx 없이 전부 돌아가요. API 키는 나중에.

`ENCRYPTION_KEY` 한 줄 채우기:
```bash
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```
(python 없으면 팀 채널에 있는 공용 키 복사)

## 3. 띄우기 (5분)

```bash
docker compose up --build
```

처음엔 이미지 받느라 3~5분. (이 PC에 5432/6333/8000 을 쓰는 다른 프로젝트가 있으면 §6 포트 충돌 항목 참고) 이게 보이면 성공:
```
api  | Application startup complete.
```

확인:
- http://localhost:8000/docs → API 목록 (Swagger)
- http://localhost:8000/health/ready → `{"postgres":true,"qdrant":true,"watsonx":"mock"}`
- http://localhost:6333/dashboard → Qdrant

프론트 할 사람은 새 터미널에서:
```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

## 4. 첫 업로드 (10분)

Swagger(http://localhost:8000/docs)에서 순서대로:

1. `POST /api/auth/signup` → 두 번 (A, B). 토큰 2개 받기
2. 오른쪽 위 **Authorize**에 A 토큰 → `POST /api/couples/invite` → `invite_code` 복사
3. Authorize를 B 토큰으로 → `POST /api/couples/join` (코드 입력)
4. Authorize를 A 토큰으로 → `POST /api/couples/{couple_id}/confirm` `{"accept": true}`
5. `POST /api/couples/{couple_id}/upload` — 파일: `api/tests/fixtures/kakao/ios.txt`, name_map: `{"a":"<이름1>","b":"<이름2>"}`
6. `GET /api/couples/{couple_id}/timeline` → 주별 숫자가 보이면 끝

또는 한 방에:
```bash
python scripts/smoke_test.py http://localhost:8000
```

## 5. 내가 할 일은 어디에

`docs/TASKS.md` §10 에 역할별 첫날 순서, `docs/SCAFFOLD.md` §3 에 "내가 건드리는 폴더"가 있어요.

| 나는… | 먼저 읽을 것 | 만질 폴더 |
|---|---|---|
| 프롬프트 | 기획서 §4, REQUIREMENTS FR-004 금지 표현 | `api/app/prompts/`, `data/knowledge/` |
| 백엔드/AI | API_SPEC, SCAFFOLD §2 | `api/app/` |
| 프론트 | API_SPEC (예시 JSON이 곧 화면 데이터) | `web/src/` |
| 인프라 | SCAFFOLD §2 openshift/, 실습 자료 | `openshift/` |
| PM | REQUIREMENTS, TEST_CASES "반드시 확인" | `docs/` |

**계약 파일 3개**(`docs/API_SPEC.md`, `api/app/models/api.py`, `web/src/api/types.ts`)는 바꾸기 전에 팀 채널에 말하기. 이게 프론트·백이 서로 기다리지 않게 하는 유일한 장치예요.

## 6. 막혔을 때

| 증상 | 원인 | 해결 |
|---|---|---|
| `api` 컨테이너가 바로 죽음, 로그에 `환경변수가 없습니다` | `AI_PROVIDER=watsonx`인데 키 없음 | `.env`에서 `AI_PROVIDER=mock`으로 |
| `port is already allocated` | 5432/6333/8000 다른 프로그램이 사용 | `docker-compose.yml`에서 **왼쪽** 포트만 바꾸기 (`15432:5432`) |
| `/health/ready`가 503, `postgres: false` | DB 아직 뜨는 중 | 10초 기다렸다 재시도. 계속이면 `docker compose logs postgres` |
| `/health/ready`가 503, `qdrant: false` | 위와 동일 | `docker compose logs qdrant` |
| 업로드 422 `UNSUPPORTED_FORMAT` | 카톡 내보내기 파일이 아님 | PC: 대화 내보내기 / iOS: **텍스트 메시지만 보내기** / Android: 대화 내용 내보내기 |
| 업로드 422 `NOT_COUPLE_CHAT` | 단톡방 파일 | 1:1 대화방 파일로 |
| 업로드 422 `NAME_MAPPING_REQUIRED` | 첫 업로드에 name_map 없음 | 응답 `detail.senders`의 이름 2개를 a/b로 지정 |
| `AI_PROVIDER=watsonx`로 바꿨는데 답변이 빈 문자열 | gpt-oss는 추론 모델 — 토큰 부족하면 생각만 하다 끝남 | `.env`에 `WATSONX_REASONING_EFFORT=low`, `WATSONX_MAX_TOKENS=2000` 확인 |
| 임베딩 검색이 엉뚱함 | `passage:`/`query:` 접두사 누락 | `ai_service.py`의 `embed_texts`/`embed_question` 사용 (직접 호출 금지) |
| 한국어 대신 영어로 답함 | 프롬프트에 언어 지시 없음 | `prompts/*.md` 첫 줄 "모든 출력은 한국어" 확인 |
| `git push` 거부, `.env` 포함 | 커밋에 키 들어감 | `git rm --cached .env` 후 재커밋. 키는 재발급 |
| Windows에서 `\r\n` 관련 파서 오류 | 에디터가 줄바꿈을 바꿈 | 카톡 파일은 **절대 에디터로 열어 저장하지 말 것**. 원본 그대로 |
| OpenShift `ImagePullBackOff` | Docker Hub 차단 | 해찬에게. 내부 레지스트리 경유 |
| OpenShift Postgres/Qdrant `permission denied /data` | SCC | 실습 `trouble_shoot/pvc_error_*.yaml` 참고 |

## 7. 지켜야 할 것 5가지

1. **`.env` 커밋 금지.** `.env.example`만
2. **LLM이 숫자를 계산하지 않는다.** 지표는 `metrics.py`
3. **리포트·챗봇 문구에 점수·등급·좋다/나쁘다·"~하세요" 금지.** `prompts/banned_patterns.txt`
4. **챗봇은 인용 없으면 답하지 않는다.** 지어내지 않는다
5. **컴포넌트에서 직접 fetch 금지.** `web/src/api/client.ts` 경유

## 8. 명세서를 보고 구현하는 법 (에이전트를 쓰든 안 쓰든)

이 리포의 `docs/`는 사람과 AI 에이전트 **둘 다** 읽으라고 쓴 명세서예요. 어떤 도구를 쓰든 작업 단위는 같습니다.

### 8.1 한 작업의 재료 찾기

작업 하나(예: "업로드 API 구현")에 필요한 문서는 보통 이 4개:

| 무엇을 | 어디서 | 예: 업로드 |
|---|---|---|
| 왜 만드는지·경계 | `REQUIREMENTS.md` FR 번호 | FR-002 |
| 입출력 계약 | `API_SPEC.md` 해당 절 + `models/api.py` / `types.ts` | API_SPEC §3, `UploadResponse` |
| 끝났다고 판정하는 기준 | `TEST_CASES.md` TC 번호 | TC-API-003 |
| 어느 파일을 만지는지 | `SCAFFOLD.md` §3, 각 파일 첫 줄 `# 역할:` 주석 | `routers/upload.py`, `services/kakao_parser.py` |

각 소스 파일 **첫 줄**에 역할과 참조 절이 적혀 있어요 (`# 역할: FR-002 업로드 … (참조: API_SPEC §3)`). 파일을 열면 어느 문서를 봐야 하는지 바로 보이게 해뒀습니다.

### 8.2 직접 구현할 때

1. 위 표대로 FR → API_SPEC → TC 순서로 읽기. API_SPEC의 **예시 JSON이 곧 정답 출력**
2. 스텁 파일의 `TODO` 자리에 구현. 응답 모델(`models/api.py`)은 이미 있으니 그대로 반환
3. `docker compose up` 후 Swagger 또는 `scripts/smoke_test.py`로 확인
4. TEST_CASES의 해당 TC 조건을 만족하는지 체크하고 PR

### 8.3 에이전트(Claude Code, Codex, Cursor 등)에게 시킬 때

프롬프트에 아래 3가지를 **항상** 넣으세요. 도구는 달라도 원리는 같아요 — 에이전트는 문서를 가리켜줘야 읽습니다.

```
docs/API_SPEC.md §3 과 docs/TEST_CASES.md TC-API-003 기준으로
api/app/routers/upload.py 의 TODO 를 구현해줘.
응답 모델은 api/app/models/api.py 의 UploadResponse 를 그대로 쓰고,
계약 파일(API_SPEC, models/api.py, types.ts)은 바꾸지 마.
```

- **범위 하나**: 라우터 하나, 화면 하나. "전부 다 만들어줘"는 디버깅이 어려워요
- **계약 파일 고정**: 바꿔야 하면 "API_SPEC도 같이 고치고, 바뀐 점을 알려줘"라고 명시
- **금지 규칙 상기**: 프롬프트·리포트 작업이면 §7의 2~4번(LLM 계산 금지, 금지 표현, 인용 없는 답변 금지)을 프롬프트에 포함
- **막히면 로그 그대로**: `docker compose logs api --tail 50` 출력을 붙여넣기
- Claude Code는 루트의 `CLAUDE.md`, Codex는 `AGENTS.md`를 자동으로 읽어요. 둘 다 없으면 위 규칙을 프롬프트에 직접 넣으면 됩니다

### 8.4 문서를 고쳐야 할 때

- 구현하다 명세가 틀렸거나 빠진 걸 발견하면 **코드와 문서를 같은 PR에서** 고치기
- 계약 파일 3개(`API_SPEC.md`, `models/api.py`, `types.ts`)는 고치기 전에 팀 채널에 먼저
- TEST_CASES에 없는 동작을 추가했으면 TC 한 줄 추가 — 다음 사람(또는 에이전트)의 완료 기준이 됩니다
