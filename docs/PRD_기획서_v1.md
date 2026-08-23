# 커플 대화 리포트 서비스 — 기획서 v1

> 프로젝트명(가칭): LOVE DIV / 연참시
> 작성일: 2026-08-22 · 상태: 개발 착수 전 · 다음 개정: 첫날 검증 결과 반영 후

---

> ## ⚠️ 읽기 전에 — 뒤집힌 내용이 있습니다 (2026-08-24 추가)
>
> 이 문서는 **2026-08-22 시점의 스냅샷**입니다. 이후 구조 검토에서 여러 결정이 바뀌었습니다.
> **현재 사양은 `REQUIREMENTS.md`·`API_SPEC.md`·`TRD.md` 가, 변경 근거는 `ISSUE.md` 가 우선합니다.**
>
> | 이 문서 | 현재 | 근거 |
> |---|---|---|
> | §2.1·§5 CronJob 주 1회 | 제거 | ISSUE D1 |
> | §3 지표 1 "대화 개시 비율" | 제거. `reply_gap` 중앙값이 그 자리 | ISSUE A2·B3 |
> | §3 "각 지표는 A·B 각각 + 커플 합산" | 응답은 `couple` + 요청자 본인 `mine` 만. 상대 값 미전송 | ISSUE B3 |
> | §4 에이전트 입력에 수치 | 코드가 `{direction, magnitude}` 로 밴딩해 전달 | ISSUE B4 |
> | §6.1 스키마 | 크게 다름. `weekly_terms`·`couple_lexicon`·`term_count_cache`·`jobs` 추가, `session_id` 는 epoch 초 | ISSUE E·B2·C7 |
> | §6.2 컬렉션 B (Qdrant) | 메모리 dict. Qdrant 는 컬렉션 A 만 | ISSUE D2 |
> | §7.1 `initiation_ratio` | 없음. 지표는 `{couple, a, b}` 로 저장 | ISSUE A2·B3 |
> | §7.2 `highlights[].who`, `moments[].who` | 응답에서 삭제 | ISSUE B3 |
> | §7.2 "A가 …28% 줄었어요" | 인물 지목·수치 금지. 관찰·해석·제안 3문장 | ISSUE B3·B4 |
> | §7.3 조언 리다이렉트 문구 | 수정됨 | ISSUE B4 |
>
> 여전히 유효하고 다른 문서에 없는 것: **§0~2**(무엇을 왜 만드는가) · **§11 미결** · **§12 검증 대기** · **§13 템플릿 매핑** · **§14 보안 메모**

---

이 문서는 팀 전원이 같은 그림을 보기 위한 기준 문서입니다. **[확정]**은 합의된 것, **[미결]**은 팀이 정해야 하는 것, **[검증 대기]**는 코드를 돌려봐야 아는 것입니다. 미결·검증 대기 항목은 끝에 한 번에 모아두었습니다.

---

## 0. 한 문장 정의

커플이 둘 다 연결한 뒤 카톡 대화를 올리면, **판정 없이** 대화 패턴의 변화를 주간 리포트로 보여주고, 과거 대화를 사실 기반으로 검색해주는 서비스.

---

## 1. 설계 원칙 [확정]

1. **판정하지 않는다.** 점수·등급·"좋다/나쁘다"·"~해야 한다" 표현 금지. 지표는 그 커플의 과거와만 비교한다(절대 기준 없음).
2. **결정론적 지표가 핵심, LLM은 해석과 문장 생성만.** 지표 계산·이상치 판정은 코드가 한다. LLM이 틀려도 지표는 흔들리지 않는다.
3. **양쪽 동의가 구조다.** 둘 다 연결돼야 리포트가 생성되고, 리포트는 양쪽에 동일하게 공개된다. 몰래 분석은 구조적으로 불가능.
4. **근거 없는 말은 하지 않는다.** 해석은 출처와 함께, 챗봇 답변은 원문 인용과 함께.
5. **원본은 저장하되 LLM엔 최소한만 보낸다.** 원본은 암호화 저장, 커플 해제·탈퇴 시 즉시 삭제. LLM에는 지표 변화 구간의 메시지만 전달.

---

## 2. 기능 정의

### 2.1 MVP (해커톤 범위) [확정]

| 기능 | 정의 | 비고 |
|---|---|---|
| 가입·커플 연결 | 가입 → 초대 코드 생성 → 상대가 코드로 연결 | 탈퇴 시 커플 해제 + 데이터 삭제 |
| 대화 업로드 | 카톡 txt 업로드 → 파싱 → 세션 분할 → 저장·적재 | 양쪽 연결 후 한쪽이 올리면 됨. 재업로드 시 메시지 해시로 중복 제거 |
| 주간 대화 리포트 | 주 단위 지표 추이 + 변화 해석 1~3개 + "이번 주 시도해볼 것" 1~2개 | **업로드 직후 과거 모든 주차를 즉시 소급 생성**(주간은 단위이지 생성 시점이 아님). 지표는 동기(즉시), 리포트는 비동기(진행률 표시). 이후 CronJob이 주 1회 지난주 분 추가. 진행 중인 주는 "진행 중" 표시 |
| 이 구간 돌아보기 | 타임라인에서 세션/날짜 선택 → 해당 구간 지표 vs 기준선 나란히 표시 + 메모 저장 | 챗봇이 여기에 붙음 |
| 대화 검색 챗봇 | 사실 질문에만 답변, 원문(날짜·발화자) 인용 필수 | 조언·판정 요청은 리포트로 리다이렉트 |

> 〔현재〕 §2.1 의 "CronJob 이 주 1회 지난주 분 추가"는 **제거**됐습니다(ISSUE D1) — 카톡 연동이 없어 새 데이터는 업로드로만 들어오고, 업로드가 이미 잡을 큐에 넣습니다.

### 2.2 로드맵 (MVP 이후) [확정]

- **기념일 리마인더**: 캘린더 + D-day 통합. 기념일 날짜는 리포트에 "생일 주간" 배지로 맥락 보정에도 활용
- **콕 찌르기 (Lv.2 프리셋)**: "삐졌어/보고싶어/혼자 있고 싶어/미안해/얘기 좀 하자" 등 카테고리 선택 → 커플이 커스터마이징한 표현으로 전달 → 상대는 리액션 3종으로 응답("알겠어 미안" / "나도 얘기하고 싶어" / "지금은 좀 그런데 이따 얘기하자"). 메시지 본문은 전달하지 않음
- **콕 찌르기 (Lv.3 자유입력 완곡화)**: 전송 전 미리보기·수정 필수. 완곡화로 내용이 바뀌는 문제 있어 후순위
- **2층 AI 지표**: 관심 표현·애정 표현·갈등 신호 빈도 (LLM 분류, "AI 추정, 오차 있음" 명시)
- **무드 체크**: 하루 1회 😊😐😞 — 장기 라벨 수집용

### 2.3 리포트에 절대 넣지 않는 것 [확정]

점수 · 등급 · 관계 온도 · 좋음/나쁨 · 원인 단정("~때문에") · 한쪽 비난 · "~해야 한다" · 이별/지속 권유 · 검색 결과에 없는 사실

---

## 3. 지표 정의 [확정]

> 〔현재〕지표 1(대화 개시 비율)은 **제거**됐고(ISSUE A2), 그 자리를 `reply_gap` 중앙값이 추이형으로 승격해 메웠습니다(ISSUE B3).
> 노출 단위도 `A·B 각각`이 아니라 `couple` + 요청자 본인 `mine` 입니다. 현재 정의는 `REQUIREMENTS.md` FR-002 표.

### 공통 전제

- 집계 단위: **주(월~일)**. 각 지표는 A·B 각각 + 커플 합산
- 추이형 지표 비교 기준: **직전 4주 평균** 대비 변화율. 4주 미만이면 비교 숨기고 절대값만 표시
- 이상치형 지표 기준선: **직전 8주 분포**, IQR × 1.5 밖이면 이상치. 상·하 양쪽 모두 보고. 8주 미만이면 이상치 판정 보류
- **세션** = 메시지 간격이 `SESSION_GAP_MIN`(기본 30분) 이상 벌어지면 새 세션 [검증 대기]

### 추이형 3개

| # | 지표 | 정의 | 함정·주의 |
|---|---|---|---|
| ~~1~~ | ~~대화 개시 비율~~ | ~~세션 첫 메시지를 보낸 사람이 A인 비율~~ | **제거됨 (ISSUE A2)** — 30분 경계에 따라 개시자가 뒤집히고 a/b 비교 프레임이라 P-1과 충돌 |
| 2 | 질문 빈도 | 본인 메시지 중 물음표 또는 의문형 어미("~야?", "~어?", "~니", "~나")로 끝나는 비율 | "뭐?", "진짜?" 같은 리액션도 잡힘 → 리포트에 "질문 형태 기준"임을 명시 |
| 3 | 발화 길이 | 본인 메시지 글자 수 **중앙값** | 사진·이모티콘·링크 플레이스홀더 제외 |

### 이상치형 2개

| # | 지표 | 정의 | 보고 형식 |
|---|---|---|---|
| 4 | 답장 간격 | 상대 메시지 → 내 첫 답장까지 시간. **세션 내에서만** 계산 | 주당 최대 3건. 발생 시각 + 평소 값 + 해당 세션 링크. 빠른 답장도 보고 |
| 5 | 세션 길이 | 세션당 메시지 수 | 주당 최대 3건. 유난히 긴/짧은 세션 모두 보고 |

**톤 규칙**: 이상치는 "문제"가 아니라 **"평소와 달랐던 순간"**으로 표현. 긍정·부정 이상치를 같은 비중으로.

### 확장 방식

지표 계산은 순수 함수(`metrics/*.py`). 새 지표 = 함수 1개 + JSON 필드 1개. 에이전트 프롬프트는 JSON을 일반적으로 읽도록 작성해 지표가 늘어도 수정 불필요.

---

## 4. 에이전트 구성 [확정]

### 에이전트가 **아닌** 것 (일반 코드)

파서 · 세션 분할 · 지표 5개 계산 · 이상치 판정 · 임베딩·Qdrant 적재 · 중복 제거. 전부 결정론적. LLM이 끼면 손해.

### 리포트 플로우 (주 1회 배치, 순차 고정)

> 〔현재〕"주 1회 배치"가 아니라 **업로드 시 변경된 주차만** 생성합니다(CronJob 제거, ISSUE D1).
> 에이전트 입력에서 **숫자가 빠졌습니다** — 코드가 `{direction, magnitude}` 로 밴딩해 넘깁니다(ISSUE B4). 선별 후보에서 `who` 축도 제거(ISSUE B3).

| 순서 | 에이전트 | 입력 | 출력 | 툴 | 규칙 |
|---|---|---|---|---|---|
| 1 | 변화 선별 | 이번 주 지표 JSON + 기준선 + 이상치 목록 + 기념일 배지 | 리포트에 올릴 변화 1~3개 + 근거 수치 | 없음 | 긍정·부정 균형, 4주 미만 항목 제외 |
| 2 | 해석 | 선별된 변화 | 변화별 **복수 해석** + 근거 메시지 1~2개 + 출처 | 컬렉션 B 검색, 컬렉션 A 검색 | 원인 단정 금지 |
| 3 | 제안 | 해석 결과 | "이번 주 시도해볼 것" 1~2개 | 제안 템플릿 풀 검색(컬렉션 B) | **자유 생성 금지**. 템플릿 선택 + 수치 치환만 |
| 4 | 안전 검수 | 1~3 출력 전체 | 통과 / 수정본 | 없음 | §2.3 금지 목록 검사. 걸리면 재작성 또는 삭제 |

### 챗봇 플로우 (실시간)

| 에이전트 | 동작 | 툴 |
|---|---|---|
| 대화 검색 | ① 질문 유형 분류 → ② 사실 질문이면 컬렉션 A 검색(메타 필터 + 벡터) → 인용 포함 답변 / 조언·판정 요청이면 리다이렉트 문구 | `search_conversation`, `get_metrics` |

안전 검수는 별도 에이전트가 아니라 **이 에이전트 내부**에 내장(응답 지연 방지). 템플릿의 "LLM route를 그대로 실행하지 않고 Supervisor가 검증 후 신뢰 Route로 재매핑" 패턴을 그대로 적용.

### 제안 문법 예시

- ✗ "질문 빈도가 줄었습니다. 상대에게 관심을 더 표현하세요."
- ✓ ~~"지난 4주 대비 서로 묻는 질문이 30% 줄었어요. …"~~
  > 〔현재〕 이 예시도 이제 그대로 쓸 수 없습니다 — **문장에 수치를 넣지 않습니다**(ISSUE B4).
  현재 형태는 관찰·해석·제안 **3문장**이고 `API_SPEC.md` §4.2 예시가 기준입니다:
  > 지난 4주에 비해 서로에게 묻는 순간이 좀 줄어들었어요.
  > 바쁜 시기였을 수도, 대화 주제가 일상 공유 쪽으로 옮겨간 걸 수도 있어요.
  > 다음엔 상대 하루에 대해 질문 하나를 더 던져보면 어떨까요.

---

## 5. 기술 스택 [확정]

교육에서 전원이 만져본 것만 사용. `academic-complaint-multi-agent` 템플릿을 포크한다.

| 레이어 | 선택 | 근거 |
|---|---|---|
| LLM | `openai/gpt-oss-120b` (watsonx.ai) | 교육 .env 기본값. 추론 모델이라 `reasoning_effort: "low"` + 토큰 여유 필수 (`rag_common.py` 참조) |
| 임베딩 | `intfloat/multilingual-e5-large` (watsonx.ai) | 교육 기본값. **`passage:` / `query:` 접두사 필수** (`_common.py` 참조) |
| 벡터 DB | **Qdrant** | 교육 전 과정이 Qdrant. 메타 필터·청크 비교·리랭킹 코드 재활용 |
| RDB | PostgreSQL 16 | 템플릿 그대로 |
| 백엔드 | FastAPI + Python Supervisor | 템플릿 포크. Orchestrate 네이티브 체인은 **쓰지 않음** (순서 고정 파이프라인이라 불필요, 미학습 리스크) |
| 프론트 | React | — |
| 배포 | OpenShift (Deployment/StatefulSet/Route/Secret/CronJob) + Tekton | 실습 자료 매니페스트 재활용 |
| 접점(선택) | watsonx Orchestrate | FastAPI `/docs` OpenAPI를 툴로 등록 가능. 나중에 결정 |

### 런타임 구성

```
React
  └─ FastAPI (agent-api)
       ├─ POST /upload          파서 → 세션 분할 → Postgres → Qdrant 적재
       │                        → 전 주차 지표 계산(동기) → 전 주차 리포트 생성(비동기 작업 큐)
       ├─ GET  /upload/{job}    소급 생성 진행률
       ├─ GET  /reports/{week}  주간 리포트 조회
       ├─ POST /chat            Supervisor → 검색 에이전트 → 인용 답변
       ├─ POST /review          구간 선택 → 지표 vs 기준선 + 메모 저장
       └─ GET  /health/ready
  CronJob (주 1회) → 리포트 플로우 4단계 → Postgres
  Qdrant  : 컬렉션 A (couple_sessions), 컬렉션 B (knowledge)
  Postgres: users / couples / messages / sessions / weekly_metrics / reports / notes
  watsonx.ai: gpt-oss-120b, multilingual-e5-large
```

### OpenShift 매핑

| compose | OpenShift | 실습 파일 |
|---|---|---|
| agent-api | Deployment + Service + Route(edge) | 06·07·08 |
| qdrant | StatefulSet + headless Service + volumeClaimTemplate | 10 |
| postgres | StatefulSet + PVC | 10·12 |
| .env | **Secret**(API 키) + ConfigMap(나머지) | 자료 없음 — 직접 작성 |
| 주간 배치 | CronJob | 자료 없음 — 짧음 |
| 빌드·배포 | Tekton Pipeline + Git 트리거 | CI/CD 자료 그대로 |

주의: 실습 StatefulSet에 "/data 쓰기 실패 시 SCC 확인" 분기가 있음 → Qdrant/Postgres 볼륨도 같은 문제 가능. `trouble_shoot/pvc_error_*.yaml` 선행 확인.

---

## 6. 데이터 설계

### 6.1 PostgreSQL 테이블 초안 [미결 — PM·AI·Back 검토 필요]

> 〔현재〕**검토 완료. 아래는 초안이고 현재 스키마는 `postgres/init.sql` 입니다.** 주요 차이:
> `weekly_terms`·`couple_lexicon`·`term_count_cache`·`jobs` 추가 / `session_id` 는 BIGSERIAL 이 아니라 **첫 메시지 epoch 초**(재업로드 시 참조 유지) /
> `messages.sender`·`sessions.initiator` 는 UUID 가 아니라 `CHAR(1)` a|b / `invite_code` 8자·7일 만료 / `status` 에 `awaiting_confirm` 추가 /
> `weekly_metrics` 는 `metrics` 대신 `summary` + `summary_hash` / `users` 참조 FK 에 `ON DELETE CASCADE`(ISSUE B2) / 세션 FK 는 `SET NULL (session_id)`(ISSUE C7)

```sql
CREATE TABLE users (
    user_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email        VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(50) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE couples (
    couple_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a       UUID NOT NULL REFERENCES users(user_id),
    user_b       UUID REFERENCES users(user_id),          -- 연결 전 NULL
    invite_code  VARCHAR(12) UNIQUE NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','active','dissolved')),
    started_at   DATE,                                    -- 사귄 날(선택)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    message_id   BIGSERIAL PRIMARY KEY,
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    sender       UUID NOT NULL REFERENCES users(user_id),
    sent_at      TIMESTAMPTZ NOT NULL,
    body_enc     BYTEA NOT NULL,                          -- 암호화된 본문
    body_len     INTEGER NOT NULL,                        -- 글자 수(지표용, 복호화 불필요)
    is_question  BOOLEAN NOT NULL DEFAULT FALSE,
    msg_type     VARCHAR(20) NOT NULL DEFAULT 'text'
                 CHECK (msg_type IN ('text','photo','emoticon','link','system')),
    msg_hash     CHAR(64) NOT NULL,                       -- sha256(sender|sent_at|body) 중복 제거
    session_id   BIGINT,                                  -- sessions 참조(적재 후 채움)
    UNIQUE (couple_id, msg_hash)
);
CREATE INDEX idx_messages_couple_time ON messages(couple_id, sent_at);

CREATE TABLE sessions (
    session_id   BIGSERIAL PRIMARY KEY,
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    started_at   TIMESTAMPTZ NOT NULL,
    ended_at     TIMESTAMPTZ NOT NULL,
    initiator    UUID NOT NULL REFERENCES users(user_id),
    msg_count    INTEGER NOT NULL,
    qdrant_point UUID                                     -- 컬렉션 A point id
);

CREATE TABLE weekly_metrics (
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start   DATE NOT NULL,                           -- 월요일
    metrics      JSONB NOT NULL,                          -- §7.1 구조
    outliers     JSONB NOT NULL DEFAULT '[]',
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, week_start)
);

CREATE TABLE reports (
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start   DATE NOT NULL,
    report       JSONB NOT NULL,                          -- §7.2 구조
    execution_trace JSONB NOT NULL DEFAULT '[]',          -- 템플릿 패턴
    status       VARCHAR(20) NOT NULL DEFAULT 'generated'
                 CHECK (status IN ('generated','failed','insufficient_data')),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, week_start)
);

CREATE TABLE notes (                                      -- "이 구간 돌아보기" 메모
    note_id      BIGSERIAL PRIMARY KEY,
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    author       UUID NOT NULL REFERENCES users(user_id),
    range_start  TIMESTAMPTZ NOT NULL,
    range_end    TIMESTAMPTZ NOT NULL,
    body         TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 로드맵용 자리만 확보 (MVP에서 미사용)
CREATE TABLE events (                                     -- 기념일
    event_id     BIGSERIAL PRIMARY KEY,
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    event_date   DATE NOT NULL,
    label        VARCHAR(50) NOT NULL,
    recurring    BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE pokes (                                      -- 콕 찌르기
    poke_id      BIGSERIAL PRIMARY KEY,
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    sender       UUID NOT NULL REFERENCES users(user_id),
    category     VARCHAR(30) NOT NULL,
    reaction     VARCHAR(30),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 6.2 Qdrant 컬렉션 [확정]

> 〔현재〕**컬렉션 B 는 Qdrant 에 두지 않습니다**(ISSUE D2). `(metric, direction)` 조합이 ~12개라 벡터 검색이 무의미해
> `data/knowledge/` 를 앱 시작 시 메모리 dict 로 로드합니다(`services/knowledge.py`). Qdrant 는 컬렉션 A 만.

**컬렉션 A `couple_sessions`** — 커플 대화 (사실 검색용)
- 청크 단위: **세션**(긴 세션은 20~30메시지로 분할)
- 벡터: e5 (`passage:` 접두사), 1024차원
- payload: `couple_id`, `session_id`, `started_at`, `ended_at`, `participants`, `msg_count`, `text`(복호화된 본문은 **Qdrant에 저장하지 않음** — point id로 Postgres 조회)
- 메타 필터: `couple_id`(필수), `started_at` 범위

**컬렉션 B `knowledge`** — 소통 지식·제안 템플릿
- 문서: 커뮤니케이션 심리 공개 자료(CC·공공기관 위주), 팀 작성 제안 템플릿 20~30개
- payload: `doc_type`(`interpretation` | `suggestion_template`), `metric`(관련 지표), `direction`(`up`|`down`|`outlier`), `source`, `text`

---

## 7. JSON 계약 (에이전트 간 인터페이스) [미결 — PM 확정 필요]

> 〔현재〕**확정됐고 이후 여러 번 바뀌었습니다.** 아래 JSON 은 초안이며, 현재 계약은
> `docs/API_SPEC.md` · `api/app/models/api.py` · `web/src/api/types.ts` 세 파일입니다(셋은 항상 같이 바뀝니다).

이 스키마가 확정돼야 코드 팀과 프롬프트 팀이 동시에 움직일 수 있다. 가장 급함.

### 7.1 `weekly_metrics.metrics`

> 〔현재〕`initiation_ratio` 없음(A2). 각 지표는 `{couple, a, b}` + `baseline_*`·`delta_*` 세 축으로 **저장**하고,
> 응답 조립 시 `{couple, mine}` 으로 투영합니다(`services/projection.py`, ISSUE B3). `reply_gap_median_min` 도 추이형에 포함.

```json
{
  "week_start": "2026-08-17",
  "data_weeks_available": 12,
  "baseline_weeks": 4,
  "session_count": 18,
  "message_count": 412,
  "metrics": {
    "initiation_ratio": {
      "a": 0.61, "b": 0.39,
      "baseline_a": 0.50,
      "delta_a": 0.11,
      "comparable": true
    },
    "question_rate": {
      "a": 0.18, "b": 0.22,
      "baseline_a": 0.25, "baseline_b": 0.24,
      "delta_a": -0.07, "delta_b": -0.02,
      "comparable": true
    },
    "message_length_median": {
      "a": 14, "b": 11,
      "baseline_a": 13, "baseline_b": 12,
      "delta_a": 1, "delta_b": -1,
      "comparable": true
    }
  },
  "outliers": [
    {
      "metric": "reply_gap",
      "who": "b",
      "session_id": 1187,
      "at": "2026-08-19T23:41:00+09:00",
      "value_min": 184,
      "baseline_median_min": 5,
      "direction": "high"
    },
    {
      "metric": "session_length",
      "session_id": 1190,
      "at": "2026-08-21T20:10:00+09:00",
      "value": 203,
      "baseline_median": 22,
      "direction": "high"
    }
  ],
  "context": {
    "events": []
  }
}
```

### 7.2 `reports.report` (리포트 플로우 최종 출력)

> 〔현재〕`highlights[].who`·`moments[].who` **삭제**(ISSUE B3). `observation` 에 인물 지목·수치 없음(B3·B4).
> `interpretations[]` 는 종결어미 없는 **절**이고 프론트가 한 문장으로 합칩니다(B4). `metrics` 는 `{couple, mine}`.

```json
{
  "week_start": "2026-08-17",
  "status": "generated",
  "highlights": [
    {
      "id": "h1",
      "metric": "question_rate",
      "who": "a",
      "observation": "지난 4주 대비 A가 묻는 질문이 28% 줄었어요.",
      "interpretations": [
        "바쁜 시기였을 수 있어요.",
        "대화 주제가 일상 공유 쪽으로 바뀌었을 수 있어요."
      ],
      "evidence": [
        {"session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?"}
      ],
      "sources": [
        {"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"}
      ],
      "sentiment": "neutral"
    }
  ],
  "suggestions": [
    {
      "id": "s1",
      "linked_highlight": "h1",
      "template_id": "q_rate_down_01",
      "text": "궁금하다면 이번 주에 하나 시도해볼 수 있어요: 상대 하루에 대해 질문 하나 더 던져보기."
    }
  ],
  "moments": [
    {
      "kind": "reply_gap_high",
      "at": "2026-08-19T23:41:00+09:00",
      "text": "화요일 밤, B의 답장이 평소(5분)보다 긴 3시간이었어요.",
      "session_id": 1187
    }
  ],
  "safety": {
    "passed": true,
    "rewritten": []
  }
}
```

**필드 규칙**
- `interpretations`는 항상 **2개 이상** (복수 해석 강제)
- `suggestions[].template_id`는 컬렉션 B에 존재하는 id여야 함 (자유 생성 방지)
- `sentiment`는 `positive | neutral | notable` 3값. `negative` 없음
- `safety.rewritten`에 검수 에이전트가 고친 문장 원본·수정본 기록 (디버그·평가용)

### 7.3 `/chat` 요청·응답

> 〔현재〕`intent` 에 `metric_query`·`report_query`·`term_count`·`other` 추가. 조언 리다이렉트 문구는 수정됐습니다 —
> 리포트도 관계를 판정하지 않으므로 "리포트를 참고하라"고 하면 헛걸음입니다(ISSUE B4). 현재 문구는 `API_SPEC.md` §6.1.
> `term_count` 는 **커플 합산만** 제공하고 발화자별로 계산·저장하지 않습니다(ISSUE A3).

```json
// 요청
{"couple_id": "...", "user_id": "...", "message": "우리 언제부터 서로 자기라고 불렀지?",
 "focus_range": {"start": null, "end": null}}

// 응답
{"intent": "fact_query",
 "answer": "2026년 3월 14일 저녁 대화에서 A가 처음 '자기야'라고 불렀어요.",
 "citations": [{"session_id": 812, "at": "2026-03-14T19:22:00+09:00", "sender": "a", "snippet": "자기야 뭐해"}],
 "redirect": null}

// 조언 요청 시
{"intent": "advice_request", "answer": null, "citations": [],
 "redirect": "이 챗봇은 대화 기록을 찾아주는 도구예요. 관계에 대한 관점은 주간 리포트를 참고해 주세요."}
```

---

## 8. 화면 목록 [미결 — Front 담당 구체화]

| 화면 | 핵심 요소 | 비고 |
|---|---|---|
| 온보딩 | 가입 → 초대 코드 표시/입력 → 연결 완료 | 연결 전엔 다른 화면 진입 불가 |
| 업로드 | txt 드롭 → 파싱 결과 요약(기간·메시지 수·세션 수) → 소급 리포트 생성 진행률 | 카톡 내보내기 방법 안내 포함 |
| 타임라인(홈) | 주 단위 가로축, 지표별 추이 그래프 3개, 이상치 마커 | 주 클릭 → 리포트, 마커 클릭 → 돌아보기 |
| 주간 리포트 | highlights 카드(관찰 + 복수 해석 + 근거 메시지), suggestions, moments | §7.2 그대로 렌더 |
| 이 구간 돌아보기 | 선택 구간 지표 vs 기준선 나란히, 챗봇 패널, 메모 입력 | 데모 클라이맥스 |
| 챗봇 | 질문 입력, 답변 + 인용 카드, 리다이렉트 안내 | 돌아보기 안에 내장 + 독립 진입 |
| 설정 | 커플 해제·탈퇴(데이터 삭제 안내) | — |

---

## 9. 데모 시나리오 초안 [미결 — PM 확정]

1. 커플 연결 완료 상태에서 시작 (온보딩은 스킵 또는 10초)
2. 6개월치 txt 업로드 → 24주 타임라인 생성
3. 최근 주 클릭 → 리포트: 질문 빈도 감소 하이라이트 + 복수 해석 + 제안 1개
4. 타임라인 이상치 마커 클릭 → "이 구간 돌아보기": 답장 간격 3시간 vs 평소 5분
5. 챗봇에 "이날 뭐가 달랐어?" → 사실만 답변 + 인용
6. 챗봇에 "우리 괜찮은 거야?" → 리다이렉트 (판정 안 함을 보여주는 장면)
7. 메모 "시험 끝나고 싸움" 저장
8. (여유 시) Mock 모드 전환해 API 없이도 흐름이 도는 것 시연

---

## 10. 팀 역할 [확정]

| 역할 | 담당 | 첫 작업 |
|---|---|---|
| PM | 김형준 | §7 JSON 계약 확정, §9 데모 시나리오, n=3 검증 주도 |
| Prompt Engineer | 문윤아 | 에이전트 4개 instructions, 제안 템플릿 풀 20~30개, §2.3 검수 규칙표, 컬렉션 B 문서 큐레이션(저작권 확인) |
| AI Engineer | 오윤석 | 파서·세션 분할·지표·이상치(결정론적 코드), Qdrant 적재·검색, Supervisor 포크 |
| Front/Back | 어시여 | React 화면 §8, FastAPI 라우트 §5 |
| SRE | 이해찬 | compose → OpenShift 매니페스트, Secret, CronJob, Tekton, 이미지 pull 확인, 원본 암호화·삭제 파이프라인 |

---

## 11. 미결 사항 (팀이 정해야 함)

| # | 항목 | 담당 | 기한 |
|---|---|---|---|
| M1 | §7 JSON 계약 확정 | PM | 개발 착수 전 |
| M2 | §6.1 테이블 검토·확정 | PM·AI·Back | 개발 착수 전 |
| M3 | **카톡 txt 파서 사양** — iOS/Android/PC 내보내기 형식 차이, 날짜 포맷, "사진"·"이모티콘"·"삭제된 메시지" 플레이스홀더, 시스템 메시지 처리. 팀원 실제 파일 3종 이상 확보 필요 | AI | 개발 착수 전 |
| M4 | §8 화면별 와이어프레임 | Front | 첫날 |
| M5 | §9 데모 시나리오 합의 | 전원 | 첫날 |
| M6 | 컬렉션 B 문서 출처 목록 (CC/공공 위주) | Prompt | 첫날 |
| M7 | 프로젝트명 확정 | 전원 | — |
| M8 | 원본 보관 기간 정책 (예: 최근 N개월만 본문 유지) | PM·SRE | 발표 전 |

---

## 12. 검증 대기 (코드를 돌려봐야 아는 것) — **첫날 오전 전부 실측**

| # | 가정 | 검증 방법 | 깨지면 |
|---|---|---|---|
| V1 | e5 임베딩이 한국어 카톡 짧은 문장에서 쓸 만하다 | "보고싶어"/"보고 싶다"/"뭐해?" 등 20문장 임베딩 → 유사도 행렬 확인. 교육 `18_compare_chunk_sizes.py` 변형 | 청크를 세션 단위로 키우거나(이미 계획), 임베딩 모델 교체 |
| V2 | 세션 분할 30분 기준이 적절하다 | 팀원 카톡 1개로 15/30/60분 세션 수 비교 | 상수 조정 |
| V3 | 지표 5개가 실제 관계 변화와 같이 움직인다 | 팀원·지인 커플 3쌍 대화로 지표 뽑고 당사자 기억과 대조 | 안 움직이는 지표 제거, 리포트 범위 축소 |
| V4 | gpt-oss-120b가 한국어 해석 문장을 자연스럽게 쓴다 | Prompt Lab에서 §7.2 highlights 생성 10회 | Llama 4 Maverick 등 비교 후 교체 |
| V5 | OpenShift에서 Docker Hub 이미지(qdrant, postgres) pull 가능 | `oc run` 테스트 | 내부 레지스트리 경유 또는 quay 미러 |
| V6 | 템플릿 Mock 모드가 우리 구조에서도 동작 | 포크 직후 `USE_MOCK=true`로 `/health/ready` | 데모 백업 플랜 재설계 |

---

## 13. 참고: 템플릿 ↔ 우리 서비스 매핑

`academic-complaint-multi-agent`를 포크할 때 대응 관계.

| 템플릿 | 우리 서비스 |
|---|---|
| 학사 규정 Agent + Qdrant 검색 | 대화 검색 챗봇 (컬렉션 A) |
| 민원 처리 Agent + `eligibility.py` | 지표 계산·이상치 판정 |
| Supervisor Intent 분류 → 신뢰 Route 재매핑 | 챗봇 사실 질문 / 조언 요청 분기 |
| `pending_action` + 승인 후 Write | (로드맵) 콕 찌르기 미리보기 → 전송 |
| `agent_sessions.state` JSONB | `reports.report` + `execution_trace` |
| `academic_chunks.json` 자동 적재 | 세션 청크 적재 |
| Mock 모드 | 데모 백업 |
| 05 VoC 모듈 테스트셋 → 리포트 | 챗봇 응답 정확도 평가 |

---

## 14. 보안 메모

- watsonx 프로젝트는 **팀 공용 1개** 생성, 팀원 5명 협업자 추가. 프로젝트 ID·API 키는 SRE가 관리 — 개발 중엔 `.env`로 공유(Git엔 `.env.example`만 커밋), OpenShift에서는 Secret으로 주입
- 공용 프로젝트에서 e5·gpt-oss-120b 호출 가능한지 `01-watsonx-env/list_models.py`로 확인
- 메시지 본문은 `body_enc`로만 저장. Qdrant payload에 본문 넣지 않음
- 커플 해제·탈퇴 → `ON DELETE CASCADE` + Qdrant `couple_id` 필터 삭제
