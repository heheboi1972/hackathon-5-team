# 처음 시작하는 사람을 위한 가이드 (GETTING_STARTED.md)

> 목표: 클론부터 첫 업로드까지 **30분**. 막히면 §6부터 보세요.

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

## 8. 스캐폴딩 (완료됨)

스캐폴딩은 2026-08-23 에 끝났어요 (`docs/SCAFFOLD.md` §5 순서 1~10, 커밋 `8052946`). 새로 합류한 사람은 §2부터 시작하면 됩니다.
참고용 — 당시 했던 것: 계약 파일(`models/api.py` ↔ `types.ts`) 1:1 작성, 라우터 8개 mock 스텁, `postgres/init.sql`, `container.py` 배선, web 초기화, `scripts/smoke_test.py`.
완료 기준은 `docs/SCAFFOLD.md` §6.

## 9. Claude Code로 작업할 때

- 프로젝트 루트에서 열기. `docs/`가 컨텍스트라 먼저 읽히게 하면 좋아요: "docs/API_SPEC.md 기준으로 routers/upload.py 구현해줘"
- 계약 파일을 바꾸는 작업은 "API_SPEC도 같이 고쳐줘"를 붙이기
- 한 번에 하나의 라우터/화면. "전부 다 만들어줘"는 디버깅이 어려워요
- 막히면 `docker compose logs api --tail 50` 결과를 그대로 붙여넣기
