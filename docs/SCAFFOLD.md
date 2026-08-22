# 스캐폴딩 설계도 (SCAFFOLD.md)

> 용도: Claude Code로 **빈 폴더에서** 스캐폴딩할 때의 지시서. §5의 프롬프트를 그대로 붙여넣으면 된다.
> 기준: docs/API_SPEC·REQUIREMENTS·TRD·TASKS. 교육 템플릿은 참고만 했고 코드 의존은 없다.

## 1. 이미 있는 것 (src/ 에 동봉 — 그대로 쓰면 됨)

| 파일 | 갈 곳 | 내용 |
|---|---|---|
| `src/kakao_parser.py` | `api/app/services/` | 카톡 파서 (PC·iOS 검증 완료) |
| `src/metrics.py` | `api/app/services/` | 세션·주간 지표·이상치 |
| `src/ai_service.py` | `api/app/services/` | watsonx/Mock 서비스. e5 접두사·gpt-oss 토큰 예산·OTel 스팬 포함 |
| `src/infra/docker-compose.yml` | 루트 | postgres·qdrant·api·web |
| `src/infra/api.Dockerfile` | `api/Dockerfile` | |
| `src/infra/web.Dockerfile`, `nginx.conf` | `web/` | 정적 빌드 + `/api` 프록시 |
| `src/infra/requirements.txt` | `api/` | 버전 고정 |

나머지는 전부 새로 만든다.

## 2. 디렉토리 트리

```
couple-report/
├── README.md                          (new) 한 줄 소개 + GETTING_STARTED 링크
├── GETTING_STARTED.md                 (new) 처음 하는 사람용 30분 가이드
├── docs/                              Day 0 산출물 그대로
│   ├── PRD_기획서_v1.md
│   ├── REQUIREMENTS.md
│   ├── API_SPEC.md
│   ├── TEST_CASES.md
│   ├── TASKS.md
│   └── SCAFFOLD.md                    이 문서
├── .env.example                       (new) 템플릿에 없음 — §4 참조
├── .gitignore                         .env, __pycache__, node_modules, .venv
├── docker-compose.yml                 postgres / qdrant / api / (web)
│
├── api/                               FastAPI 백엔드 (템플릿 api/ 기반)
│   ├── Dockerfile
│   ├── requirements.txt               + pyjwt, passlib[bcrypt], cryptography, python-multipart, instana, opentelemetry-api (TRD §2.1, §9.1)
│   ├── app/
│   │   ├── main.py                    lifespan에서 container 생성, 라우터 등록, CORS
│   │   ├── config.py                  §4 값으로 기본값 변경
│   │   ├── container.py               services + agents + supervisors 묶음
│   │   ├── routers/                   (new, 템플릿 routes.py 분할)
│   │   │   ├── auth.py                FR-000  POST signup/login
│   │   │   ├── couples.py             FR-001  invite/join/confirm/me/delete
│   │   │   ├── upload.py              FR-002  POST upload, GET jobs/{id}
│   │   │   ├── timeline.py            FR-003  GET timeline
│   │   │   ├── reports.py             FR-004  GET reports/{week}, POST regenerate
│   │   │   ├── review.py              FR-005  GET review, POST/DELETE notes
│   │   │   ├── chat.py                FR-006  POST chat
│   │   │   └── health.py              live/ready
│   │   ├── models/
│   │   │   ├── api.py                 API_SPEC 요청/응답 Pydantic — **프론트 fixture와 1:1**
│   │   │   ├── domain.py              DB 행 dataclass (Couple, Message, Session, WeeklyMetric, Report, Note)
│   │   │   └── report.py              (new) §7.2 리포트 JSON 스키마 (에이전트 간 계약)
│   │   ├── services/
│   │   │   ├── ai_service.py          Mock/watsonx, embed(passage:/query:), generate(reasoning_effort=low)
│   │   │   ├── postgres_service.py    연결 풀 + repo 함수들 (couples, messages, metrics, reports, notes)
│   │   │   ├── qdrant_service.py      컬렉션 A/B 관리, upsert, search(couple_id 필터), delete_by_couple
│   │   │   ├── kakao_parser.py        (new, 있음) src/kakao_parser.py 이식
│   │   │   ├── metrics.py             (new, 있음) src/metrics.py 이식
│   │   │   ├── crypto.py              (new) 본문 암호화/복호화 (Fernet, 키는 env)
│   │   │   ├── auth.py                (new) JWT 발급/검증, 비밀번호 해시
│   │   │   └── jobs.py                (new) 인메모리 작업 큐 (asyncio) — 리포트 소급 생성
│   │   ├── tools/                     에이전트가 호출하는 함수 (API_SPEC §8)
│   │   │   ├── search_conversation.py
│   │   │   ├── get_metrics.py
│   │   │   ├── get_report.py
│   │   │   ├── search_knowledge.py
│   │   │   └── get_suggestion_templates.py
│   │   ├── agents/
│   │   │   ├── base.py                (new) 공통: prompt 로드, JSON 파싱, 재시도, trace 기록, OTel 스팬 `agent.<name>`
│   │   │   ├── report_supervisor.py   (new) 선별→해석→제안→검수 순차 실행
│   │   │   ├── select_agent.py        (new) 에이전트 1
│   │   │   ├── interpret_agent.py     (new) 에이전트 2
│   │   │   ├── suggest_agent.py       (new) 에이전트 3
│   │   │   ├── safety_agent.py        (new) 에이전트 4
│   │   │   └── chat_supervisor.py     (new) intent 분류 → 툴 → 인용 강제 → 리다이렉트
│   │   ├── prompts/                   (new) 에이전트별 instructions — **윤아가 여기만 편집**
│   │   │   ├── select.md
│   │   │   ├── interpret.md
│   │   │   ├── suggest.md
│   │   │   ├── safety.md
│   │   │   ├── chat_intent.md
│   │   │   ├── chat_answer.md
│   │   │   └── banned_patterns.txt    금지 표현 regex (FR-004)
│   │   └── utils/
│   │       └── json_utils.py
│   ├── tests/
│   │   ├── fixtures/kakao/            pc.txt, ios.txt, android.txt (익명화)
│   │   ├── test_parser.py             TC-PARSE 일부
│   │   ├── test_metrics.py            TC-METRIC 일부
│   │   └── test_mock_flow.py          Mock 모드 업로드→리포트→챗봇 1회
│   └── mock/                          (new) Mock 모드 고정 응답
│       ├── report_generated.json      API_SPEC §4.2 예시
│       ├── chat_fact.json
│       └── chat_advice.json
│
├── data/
│   └── knowledge/                     (new) 컬렉션 B 원본 — **윤아가 여기만 편집**
│       ├── interpretations/*.md       소통 지식 문서 (frontmatter: metric, direction, source)
│       └── templates.json             제안 템플릿 풀 [{template_id, metric, direction, text}]
│
├── postgres/
│   └── init.sql                       기획서 §6.1 (users/couples/messages/sessions/weekly_metrics/reports/notes/events/pokes)
│
├── scripts/
│   ├── seed_knowledge.py              (new) data/knowledge → 컬렉션 B 적재
│   ├── smoke_test.py                  업로드→타임라인→리포트→챗봇 1회 (TC-INT-001 축약)
│   └── anonymize_kakao.py             (new) 실 카톡 파일 이름·본문 익명화 (fixture 생성용)
│
├── web/                               Vite + React 18 + TS + Tailwind/shadcn + TanStack Query + Recharts (TRD §2.2) — **시여가 여기만 편집**
│   ├── package.json
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts              fetch 래퍼 + 토큰. **컴포넌트에서 직접 fetch 금지**
│   │   │   ├── types.ts               API_SPEC 응답 타입 (models/api.py와 1:1)
│   │   │   └── mock/                  API_SPEC 예시 JSON. `VITE_USE_MOCK=true`면 client가 이걸 반환
│   │   ├── pages/
│   │   │   ├── Onboarding.tsx         가입 → 초대코드 → 수락대기 → 수락
│   │   │   ├── Upload.tsx             드롭 → 이름 매핑 → 진행률
│   │   │   ├── Timeline.tsx           주 단위 그래프 + 이상치 마커
│   │   │   ├── Report.tsx             summary / highlights / suggestions / moments
│   │   │   ├── Review.tsx             구간 선택 → 지표 vs 기준선 → 메모 + 챗봇 패널
│   │   │   └── Settings.tsx           해제
│   │   ├── components/
│   │   │   ├── ui/                    Button, Card, Modal, Badge(a/b)
│   │   │   ├── MetricChart.tsx
│   │   │   ├── HighlightCard.tsx
│   │   │   ├── MomentCard.tsx
│   │   │   └── ChatPanel.tsx
│   │   └── lib/
│   │       └── names.ts               "a"/"b" → display_name 치환
│   └── Dockerfile                     (nginx 정적 서빙, OpenShift용)
│
└── openshift/                         (new) — **해찬이 여기만 편집**
    ├── 00-namespace-secret.yaml       Secret(WATSONX_API_KEY, POSTGRES_PASSWORD, ENCRYPTION_KEY) + ConfigMap
    ├── 10-postgres-statefulset.yaml   실습 10번 치환
    ├── 11-qdrant-statefulset.yaml     실습 10번 치환
    ├── 20-api-deployment.yaml         실습 06·07 치환, envFrom Secret/ConfigMap
    ├── 21-api-route.yaml              실습 08
    ├── 30-web-deployment.yaml
    ├── 31-web-route.yaml
    ├── 40-report-cronjob.yaml         주 1회 리포트
    └── tekton/                        CI/CD 실습 복사, git-url·image만 치환
```

## 3. 역할별 "내가 건드리는 곳"

| 담당 | 편집 범위 | 건드리지 않는 곳 |
|---|---|---|
| 윤석 (AI) | `api/app/{routers,services,tools,agents,models}` | prompts/, web/, openshift/ |
| 윤아 (Prompt) | `api/app/prompts/*`, `data/knowledge/*`, `services/ai_service.py`의 모델 파라미터 | routers, web |
| 시여 (Front/Back) | `web/*`, `api/app/routers/review.py` | agents, prompts |
| 해찬 (SRE) | `openshift/*`, `docker-compose.yml`, `Dockerfile`, `.env.example` | app 코드 |
| 형준 (PM) | `docs/*`, `api/mock/*`(데모 응답), `scripts/smoke_test.py` | 코드 |

충돌 방지 규칙: 계약 파일(`models/api.py`, `web/src/api/types.ts`, `docs/API_SPEC.md`)은 **변경 전 팀 채널에 알림**.

## 4. `.env.example` (템플릿에 없어서 새로 만듦)

```env
# ---- 모드 ----
AI_PROVIDER=mock                 # mock | watsonx   ← 처음엔 mock으로 전체 확인
APP_ENV=local
LOG_LEVEL=INFO

# ---- watsonx (팀 공용 프로젝트) ----
WATSONX_API_KEY=
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=openai/gpt-oss-120b                      # 템플릿 기본값(granite)과 다름!
WATSONX_EMBEDDING_MODEL_ID=intfloat/multilingual-e5-large # 템플릿 기본값(granite-embedding)과 다름!
WATSONX_REASONING_EFFORT=low                              # gpt-oss 빈 응답 방지
WATSONX_MAX_TOKENS=2000

# ---- 저장소 ----
POSTGRES_DSN=postgresql://couple:couple@postgres:5432/couple_report
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_CONV=couple_sessions
QDRANT_COLLECTION_KNOWLEDGE=knowledge

# ---- 앱 ----
JWT_SECRET=change-me
ENCRYPTION_KEY=                  # python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
SESSION_GAP_MIN=30
ALLOWED_ORIGINS=http://localhost:5173
SEED_KNOWLEDGE_ON_START=true

# ---- 관측성 (Instana, 로컬은 비움) ----
AUTOWRAPT_BOOTSTRAP=                 # OpenShift에서 instana
INSTANA_AGENT_HOST=                  # OpenShift에서 노드 IP 또는 agent 서비스
INSTANA_SERVICE_NAME=couple-report-api
```

`config.py`는 이 파일과 1:1. 추가로 `mock_dir: Path = Path("/app/mock")`.

## 5. Claude Code 지시문 (복붙용)

```
빈 프로젝트다. docs/ 에 기획·계약·설계 문서가 있고 src/ 에 완성된 파일 몇 개가 있다.
docs/SCAFFOLD.md 의 §1~§4 와 docs/TRD.md 대로 스캐폴딩해줘.

순서:
1. §1 표대로 src/ 의 파일들을 제자리로 옮긴다 (src/ 는 비우고 삭제)
2. §2 트리대로 디렉토리·파일 생성. 각 파일 상단에 역할 주석 1줄과 참조 FR/API_SPEC 섹션
3. api/app/config.py 를 §4 .env.example 과 1:1 로 pydantic-settings 로 작성 (mock_dir, watsonx_reasoning_effort 포함)
4. postgres/init.sql 을 docs/PRD_기획서_v1.md §6.1 + docs/TRD.md §4.1 jobs 테이블로 작성
5. api/app/models/api.py 를 docs/API_SPEC.md 의 요청/응답대로 Pydantic 모델로 작성
6. routers/ 각 파일에 API_SPEC 엔드포인트를 스텁으로 — Mock 모드에서는 api/mock/*.json 또는 고정값 반환
7. config.py 기본값을 §4 로, .env.example 생성
8. web/ 는 Vite+React+TS 로 초기화하고 TRD §2.2 스택(React Router, TanStack Query, Tailwind+shadcn, Recharts, react-hook-form+zod) 설치. src/api/types.ts 를 models/api.py 와 1:1 로, mock/ 에 API_SPEC 예시 JSON
9. api/app/main.py: lifespan 에서 settings → ai_service(build_ai_service) → postgres pool → qdrant client → 컬렉션 보장 → container. 라우터 등록, CORS. AI_PROVIDER=mock 으로 `docker compose up` 후 /health/ready 와 /docs 가 뜨는지 확인
10. scripts/smoke_test.py 를 업로드→타임라인→리포트→챗봇 순으로 수정 (Mock 모드로 통과해야 함)

주의:
- TDD 하지 않는다. 테스트 파일은 tests/ 의 3개만 최소로
- 에이전트 4개와 chat_supervisor 는 인터페이스(입력/출력 dataclass)와 Mock 분기만, 실제 프롬프트 호출은 TODO
- agents/base.py, services/ai_service.py, tools/* 에 TRD §9.1 규약대로 OpenTelemetry 스팬을 넣는다 (instana 미설치 환경에서도 no-op으로 동작해야 함)
- prompts/*.md 는 제목과 "TODO: 윤아" 한 줄만
- 컴포넌트에서 직접 fetch 금지, client.ts 경유
- .env 는 절대 커밋하지 않는다
```

## 6. 스캐폴딩 완료 기준

- [ ] `docker compose up` → `GET /health/ready` 200 (`watsonx: "mock"`)
- [ ] `GET /docs` 에 API_SPEC 엔드포인트 17개 전부 보임
- [ ] Mock 모드로 `scripts/smoke_test.py` 통과
- [ ] `web/` `npm run dev` → 온보딩 화면 렌더 (Mock)
- [ ] `python -m app.services.metrics tests/fixtures/kakao/ios.txt` 실행됨
- [ ] `.env` 가 `.gitignore` 에 있고 `.env.example` 만 커밋됨
