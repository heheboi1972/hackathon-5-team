# 커플 대화 리포트 — 요구사항 명세 (REQUIREMENTS.md)

> 상태: v0.1 · 기준: 기획서 v1. 모든 다른 문서는 이 문서의 ID(FR/NFR/US)를 참조한다.

## 0. 설계 원칙 (모든 FR에 우선)

| ID | 원칙 |
|---|---|
| P-1 | **판정하지 않는다.** 점수·등급·좋다/나쁘다·"~해야 한다"·원인 단정·한쪽 비난·이별/지속 권유 금지 |
| P-2 | **지표는 결정론적.** 지표 계산·이상치 판정은 코드. LLM은 해석·문장 생성만 |
| P-3 | **양쪽 동의가 구조.** 상호 수락 후 활성화. 리포트는 양쪽 동일 공개. 두 사람의 값을 **나란히 놓지 않는다** — 지표는 `couple`+`mine`, 단어는 본인 것만, 챗봇 단어 횟수는 커플 합산만(발화자별 미계산). 상대 값은 응답에 담지 않으며, 노출값이 전부 중앙값·풀링 비율이고 사람별 메시지 수가 없어 역산도 불가 |
| P-4 | **근거 없는 말은 하지 않는다.** 해석은 출처, 챗봇은 원문 인용 필수 |
| P-5 | **원본은 암호화 저장, LLM엔 최소 전달.** 해제·탈퇴 시 즉시 삭제. 예외: 단어 단위 집계 테이블(`weekly_terms`, `couple_lexicon`, `term_count_cache`)은 평문 — 원문 복원 불가, 해제 시 CASCADE 삭제 |

---

## 1. 기능 요구사항 (Functional Requirements)

### FR-000: 회원 가입·로그인

**API**: `POST /api/auth/signup`, `POST /api/auth/login`

| 필드 | 제약 | 에러 메시지 |
|---|---|---|
| email | 형식, unique | "이메일 형식을 확인해주세요" / "이미 가입된 이메일이에요" |
| password | 8자 이상 | "비밀번호는 8자 이상이에요" |
| display_name | 1~20자 | "이름을 입력해주세요" |

---

### FR-001: 커플 연결

**API**: `POST /api/couples/invite`, `POST /api/couples/join`, `POST /api/couples/{id}/confirm`, `GET /api/couples/me`, `DELETE /api/couples/{id}`

**상태 전이**: `pending` → `active` → `dissolved`

**처리 규칙**
- 한 사용자는 동시에 하나의 `active`/`awaiting_confirm` 커플에만 속한다
- 초대 코드: 8자, 7일 만료, `pending` 동안 재사용
- 상대방이 코드 입력하면 즉시 `active`; 초대자 화면도 상태 확인을 통해 완료로 전환
- 양쪽이 코드를 발급했어도 한쪽 코드를 입력하면, 입력한 쪽의 미사용 코드는 폐기하고 연결
- 해제(DELETE) 시 커플의 메시지·세션·지표·리포트·메모·Qdrant 포인트 **즉시 삭제** (P-5)
- `active` 아니면 업로드·리포트·챗봇 모두 403

**검증 에러**

| 조건 | 코드 |
|---|---|
| 이미 커플 있음 | ALREADY_COUPLED |
| 자기 코드 | INVITE_SELF |
| 코드 없음/만료 | INVITE_INVALID |
| 상태 불일치 | INVITE_STATE |

---

### FR-002: 대화 업로드·파싱·지표 계산

**API**: `POST /api/couples/{id}/upload`, `GET /api/jobs/{id}`

**입력**: `.txt`(PC·iOS·Android) 또는 `.zip`(iOS 도큐멘트, 내부 txt만 사용). 최대 50MB

**처리 규칙**
1. 형식 감지 (PC / iOS / Android). 실패 → UNSUPPORTED_FORMAT
2. 파싱 → `{sender, sent_at, body, msg_type, is_question, body_len, tokens}` (파서 사양: `services/kakao_parser.py` 와 TC-PARSE-001~004. 기획서에는 §15 가 없고 **M3 미결 항목**으로만 잡혀 있었다. `tokens`는 단어 집계용, 저장 안 함)
3. 발화자 ≠ 2명 → NOT_COUPLE_CHAT
4. 카톡 이름 → A/B 매핑. 최초 업로드는 `name_map` 필수 (NAME_MAPPING_REQUIRED)
5. `sha256(sender|sent_at|body)`로 중복 제거, 신규만 저장. 본문은 암호화 (P-5)
6. **동기**: 세션 분할(간격 ≥ `SESSION_GAP_MIN`, `session_id` = 시작 시각 epoch 초) → `sessions` upsert → **`messages.session_id` 채우기**(5에서 NULL 로 INSERT 된 것을 세션 생성 후 UPDATE — FK 때문에 순서가 고정된다. 안 채우면 조용히 NULL 로 남아 인용·evidence·돌아보기 조회가 빈다) → 전 주차 지표 계산 → `weekly_metrics` upsert(`summary_hash`) → `weekly_terms` 집계(시드 사전 + `couple_lexicon`)
7. **비동기**: (a) `embed_sessions` — 신규·변경 세션 Qdrant 적재, 먼저 실행 (b) `report_backfill` — 리포트 생성 (c) `build_lexicon`(Phase 3) — 커플 단어 LLM 분류. 각각 `job_id`, 진행률 조회 가능
8. 재업로드 시 `summary_hash`가 바뀐 주차만 리포트 재생성. 리포트의 baseline은 생성 시점 스냅샷(하류 주차 자동 재생성 없음)

**지표 정의** (기획서 §3, `metrics.py`)

| 지표 | 종류 | 정의 |
|---|---|---|
| question_rate | 추이 | text 메시지 중 질문 비율 (couple = 두 사람 메시지를 합친 뒤의 비율, 사람별 비율의 평균 아님). 질문 = (1) `?`로 끝남(뒤 ㅋ/ㅎ/~ 허용) (2) 의문사(뭐·언제·어디·누구·왜·어떻게·몇·얼마…) + 구어 어미(어/아/야/지/요/해/와…) 또는 의문사 단독 (3) 강한 어미(니·냐·까·까요·나요·을까, "아니"·"할까 말까" 제외). `!`로 끝나면 비질문. 형태소 분석 없음 — "괜찮아" 류 동형은 물음표 없으면 평서문 |
| message_length_median | 추이 | text 메시지 글자 수 중앙값 (couple = 두 사람을 합친 분포의 중앙값) |
| reply_gap | **추이 + 이상치** | 세션 내 상대 메시지 → 내 첫 답장. 중앙값(couple = 양방향 전체)은 추이형으로 기준선·delta 보유, 개별 건은 이상치 판정에 계속 사용. A2 로 `initiation_ratio` 가 빠진 자리 |
| resume_delay | 이상치 | 세션 경계에서 상대가 답하며 재개하기까지 (≤12h) |
| session_length | 이상치 | 세션당 메시지 수 |
| activity | 집계 | 요일(0=월)×7·시간대×24 메시지 수(커플 합산) + `top_weekday`·`top_hour` |
| sentiment ("내 단어") | 집계 | 사전(`couple_lexicon`) 매칭 단어를 사람별·주별로 센 긍정/부정 상위 3 (`count<3` 숨김). 앞 2토큰 부정어(안/못/별로/전혀)·뒤 "지 않/지 마"는 제외. 철자 변형은 canonical로 합산, 동의어 분리. **본인 것만 응답** (P-3 예외). 단어 단위라 반어·문맥은 반영 안 됨 |

- 추이형 기준선: 직전 4주 평균, `couple`·`a`·`b` 각각 계산. `comparable` 은 **couple 기준** 하나 (4주 미만 `false`)
- 노출: 추이 지표는 `couple` + `mine`(요청자 본인)만 응답에 담는다. 저장은 사람별, 투영은 응답 조립 시점 (P-3, ISSUE B3)
- 이상치: 직전 8주 분포, log-IQR×1.5 밖 **그리고** 기준선 중앙값의 3배 이상/⅓ 이하. 표본 20 미만 보류. 지표·사람당 주 3건. **판정은 사람별 분포를 유지**하고(합치면 서로 다른 평소 속도가 섞여 오판정), 응답에서 발화자만 제거

---

### FR-003: 타임라인 조회

**API**: `GET /api/couples/{id}/timeline`

- 전 주차 `summary`(현황 숫자) + `report_status` + `outlier_count` + `events`
- 진행 중인 주는 `in_progress=true`
- 리포트 본문은 포함하지 않음 (FR-004)

---

### FR-004: 주간 리포트 생성·조회

**API**: `GET /api/couples/{id}/reports/{week_start}`, `POST .../regenerate`

**리포트 구조** (API_SPEC §4.2)
- `summary`: 현황 숫자. **항상** 존재. 코드 생성, LLM 미경유
- `metrics`: 추이형 3개(`question_rate`, `message_length_median`, `reply_gap_median_min`) + 기준선 + delta + comparable. 각각 `couple`·`mine`
- `highlights`: 변화 1~3개. `comparable` 주차만. 각각 관찰 + **해석 ≥2개** + 근거 메시지 + 출처. **발화자를 지목하지 않고 `couple` 값만 근거로 삼는다** (ISSUE B3)
- `suggestions`: 1~2개. 템플릿 풀에서 선택만 (자유 생성 금지). `template_id` 존재 보장
- `moments`: 이상치 최대 3건. "평소와 달랐던 순간" 톤. 긍정·부정 동등 비중
- `safety`: 검수 통과 여부 + 재작성 기록

**생성 파이프라인** (기획서 §4): 변화 선별 → 해석 → 제안 → 안전 검수. 순차 고정. Python Supervisor

**LLM 입력 경계**: 에이전트에는 **숫자를 넘기지 않는다**. 코드가 `couple` 값과 기준선을 `{direction: up|down|steady, magnitude: slight|clear}` 로 밴딩해서 넘긴다 (`metrics.band`, 결정론 — P-2). `mine`·사람별 delta 도 넘기지 않는다. 비교 문장도 지어낸 수치도 재료 자체가 없다 (P-1, ISSUE B3). 수치는 타임라인 그래프가 담당 — **문장은 정성, 숫자는 그래프**

**금지 표현** (P-1, 검수 에이전트 규칙표)

| 범주 | 예 |
|---|---|
| 점수·등급 | "72점", "A등급", "관계 온도" |
| 가치 판단 | "좋아졌어요", "나빠졌어요", "건강한", "위험한" |
| 단정 | "~때문에", "~해야 해요", "~하세요" |
| 비난 | "B가 무심해요", "A가 노력하지 않아요" |
| 관계 판정 | "헤어지는 게", "잘 맞아요" |
| 근거 없는 사실 | 검색 결과·지표에 없는 내용 |

**상태**: `generated` / `insufficient_baseline`(4주 미만: summary만) / `pending` / `failed`

---

### FR-005: 이 구간 돌아보기 + 메모

**API**: `GET /api/couples/{id}/review`, `POST/DELETE .../notes`

- 사용자가 세션 또는 구간(≤14일) 선택 → 구간 지표 vs 직전 8주 기준선 나란히
- 메모: 1~500자, 작성자만 삭제. 리포트 생성 시 해석 에이전트 입력에 포함 (맥락 보정)
- 챗봇 호출 시 `focus_range`로 전달

---

### FR-006: 대화 검색 챗봇

**API**: `POST /api/couples/{id}/chat`

**의도 분류** (Supervisor, 신뢰 Route 재매핑)

| intent | 동작 | 툴 |
|---|---|---|
| fact_query | 컬렉션 A 검색 → 인용 답변 | search_conversation |
| metric_query | 지표 수치 답변 | get_metrics |
| report_query | 과거 리포트 내용 답변 | get_report |
| term_count | 단어 등장 횟수 (커플 합산) | count_term |
| advice_request | **고정 리다이렉트**, answer=null | 없음 |
| other | 안내 문구 | 없음 |

**불변 규칙**
- 인용 0건이면 답변 폐기 → "관련 기록을 찾지 못했어요" (P-4)
- advice_request는 LLM 답변 생성 자체를 하지 않음 (P-1)
- 인용은 `{session_id, at, sender, snippet}` 필수. 단 `term_count` 는 예외 — 숫자·주별 추이가 근거이고 인용을 붙이지 않는다(발화자 노출 방지)
- `term_count` 는 **커플 합산만** 제공한다. 발화자별 횟수는 계산·저장하지 않는다 (P-3 예외 보호)

---

### FR-007 (로드맵): 기념일 리마인더 · FR-008 (로드맵): 콕 찌르기 Lv.2 · FR-009 (로드맵): 2층 AI 지표

MVP 제외. 스키마 자리만 (`events`, `pokes`).
- 주 1회 자동 리포트(CronJob): 주기적 데이터 유입(카톡 연동 등)이 생기면. 지금은 업로드가 잡을 큐에 넣으므로 불필요
- 감성 단어 문맥 검증(표시 후보 등장 건마다 LLM keep/drop, `term_verdict` 캐시): 리허설에서 오분류가 거슬리면

---

## 2. 비기능 요구사항

| ID | 항목 | 요구 |
|---|---|---|
| NFR-001 | 성능 | 업로드 동기 구간(파싱+지표) 18k 메시지 기준 10초 이내. 타임라인·리포트 조회 500ms 이내. 챗봇 응답 8초 이내 |
| NFR-002 | 비동기 | 리포트 소급 생성은 작업 큐. 진행률 조회 가능. 부분 실패 시 나머지 계속 |
| NFR-003 | Mock 모드 | `USE_MOCK=true`면 watsonx 없이 전 흐름 동작 (데모 백업) |
| NFR-004 | 데이터 보호 | 본문 암호화 저장. Qdrant payload에 본문 미저장. 해제 시 즉시 삭제. API 키는 Secret |
| NFR-005 | 관측성 | 리포트·챗봇 응답에 `execution_trace`/`trace_id`. 에이전트 단계별 입출력 기록 |
| NFR-006 | 배포 | OpenShift (Deployment/StatefulSet/Route/Secret), Tekton 빌드 |
| NFR-007 | 한국어 | 모든 사용자 노출 문구 한국어. LLM 출력 한국어 강제 |
| NFR-008 | 확장 | 지표 추가 = 함수 1 + JSON 필드 1. 에이전트 프롬프트 수정 불필요 |

---

## 3. 사용자 스토리

### US-001: 커플 연결
> 커플로서, 상대와 함께 동의한 뒤에만 서비스를 시작할 수 있다. 그래서 한쪽이 몰래 분석하는 일이 없다.

- [ ] A가 초대 코드를 만들어 B에게 전달한다
- [ ] B가 코드를 입력하면 A에게 수락 요청이 표시된다
- [ ] A가 수락해야 서비스 진입이 가능하다
- [ ] 어느 쪽이든 해제하면 모든 데이터가 삭제된다

**FR**: FR-001

### US-002: 대화 업로드
> 커플로서, 카톡 내보내기 파일을 올리면 바로 지표가 계산된다.

- [ ] PC·iOS·Android 내보내기 파일을 올릴 수 있다
- [ ] 카톡 이름을 A/B에 연결한다
- [ ] 업로드 직후 타임라인이 뜨고, 리포트는 순차적으로 채워진다
- [ ] 같은 파일을 다시 올려도 중복되지 않는다

**FR**: FR-002, FR-003

### US-003: 타임라인으로 흐름 보기
> 커플로서, 주 단위 지표 추이를 한 그래프에서 본다.

- [ ] 지표 3개 추이 그래프 + 이상치 마커
- [ ] 주 클릭 → 리포트, 마커 클릭 → 돌아보기

**FR**: FR-003

### US-004: 주간 리포트 읽기
> 커플로서, 이번 주 대화가 평소와 어떻게 달랐는지 판정 없이 본다.

- [ ] 현황 숫자가 항상 보인다
- [ ] 변화 하이라이트마다 해석이 2개 이상, 근거 메시지가 붙는다
- [ ] "시도해볼 것"이 1~2개, 명령형이 아니다
- [ ] 점수·등급·좋다/나쁘다가 어디에도 없다
- [ ] 4주 미만이면 현황만 보이고 그 이유가 표시된다

**FR**: FR-004

### US-005: 특정 구간 돌아보기
> 커플로서, 뭔가 있었던 날을 골라 평소와 비교하고 메모를 남긴다.

- [ ] 세션/구간 선택 → 지표 vs 기준선
- [ ] 메모 저장·삭제
- [ ] 같은 화면에서 챗봇에 물을 수 있다

**FR**: FR-005, FR-006

### US-006: 대화 기록 검색
> 커플로서, "우리 언제 ~했지?"를 물으면 원문과 날짜로 답을 받는다.

- [ ] 사실 질문에 인용 포함 답변
- [ ] 지표·과거 리포트 질문에 답변
- [ ] 조언 요청은 리포트로 안내된다
- [ ] 찾지 못하면 지어내지 않는다

**FR**: FR-006

---

## 4. 추적 매트릭스 (US ↔ FR ↔ TC)

| US | FR | TC |
|---|---|---|
| US-001 커플 연결 | FR-001 | TC-API-001, TC-API-002, TC-INT-001 |
| US-002 업로드 | FR-002, FR-003 | TC-PARSE-001~004, TC-METRIC-001~005, TC-API-003, TC-API-004 |
| US-003 타임라인 | FR-003 | TC-API-004 |
| US-004 리포트 | FR-004 | TC-API-005, TC-AGENT-001~004, TC-INT-002 |
| US-005 돌아보기 | FR-005, FR-006 | TC-API-006, TC-API-007, TC-INT-003 |
| US-006 챗봇 | FR-006 | TC-API-008, TC-AGENT-005, TC-INT-003 |

---

## 5. 용어

| 용어 | 정의 |
|---|---|
| 세션 | 메시지 간격 ≥ `SESSION_GAP_MIN`(30분)으로 구분되는 대화 덩어리 |
| 주 | 월~일. `week_start`는 월요일 |
| 기준선 | 추이형: 직전 4주 평균 / 이상치형: 직전 8주 분포 |
| 현황(summary) | 기준선 없이 해당 주 절대값. 코드 생성 |
| 하이라이트 | 기준선 대비 변화 중 선별된 1~3개 |
| 모먼트 | 이상치. "평소와 달랐던 순간" |
| 컬렉션 A | Qdrant `couple_sessions` — 커플 대화 세션 청크 |
| 컬렉션 B | Qdrant `knowledge` — 소통 지식 문서 + 제안 템플릿 |
