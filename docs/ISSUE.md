# ISSUE.md — 미결 문제점 작업 목록 (임시)

> **임시 문서.** 2026-08-23 구조 검토에서 나온 미결 항목. 하나씩 결론 내고 `[x]` 체크, `결정:` 줄에 결론 기록. 전부 해결되면 이 파일은 삭제.
> 항목 형식: 문제 → 선택지 → 영향 파일 → 결정

---

## A. 결정 필요

### A1. [x] 감성 사전 방식
- **문제**: 긍정/부정 단어 상위 3개(사람별) 기능에 쓸 사전을 어떻게 만들 것인가. 고정 사전은 오타·변형(`조아`, `짱나`, `좋앙`)을 못 잡아 실제 빈도의 절반 이하만 셈.
- **선택지**
  - (a) 수작업 사전 50~100개 (`data/knowledge/sentiment_lexicon.json`, 윤아). 단순, 즉시, 결정론. 변형 미커버.
  - (b) 커플별 빈도 상위 ~500 단어 → LLM 1회 분류+정규화(canonical) → `couple_lexicon` 테이블에 append-only 누적 → 코드가 카운트. ~4천 토큰/커플. 변형·오타 커버. 비동기 잡 1종·테이블 1개·프롬프트 1개 추가, sentiment가 비동기 지표가 됨.
  - (c) Phase 2는 (a)로 먼저 돌리고, Phase 3에 (b)를 얹음. (a)의 사전을 `couple_lexicon` 공용 시드로 재사용.
- **영향**: `init.sql`, `metrics.py`, `jobs.kind`, `API_SPEC` §3.1/§4.x, `prompts/`, TASKS 1-8·2-3·3-x
- **결정**: **(b) 채택 + 문맥 예시 + 코드 부정어 규칙.**
  1. 코드: 토크나이즈(반복문자 축약·조사 제거) → 주차·사람별 빈도 집계 → 커플 전체 빈도 상위 ~500 단어. 단어마다 **최초 등장 3건**의 앞뒤 2~3토큰 예시를 결정론적으로 추출
  2. LLM 1회(100단어씩 분할, ~18k 토큰): 단어 + 예시 → `{term, canonical, polarity: pos|neg|neutral|exclude}`. exclude = 욕설·이름·식별정보. canonical은 **철자 변형만** 묶음(A5)
  3. `couple_lexicon(couple_id, term, canonical, polarity)` **append-only** — 한 번 분류된 단어는 재분류 안 함(재현성). 공용 시드 사전 30~50개를 초기값으로 항상 적용(LLM 실패·비동기 공백 대비)
  4. 코드 카운트: 앞 2토큰에 `안/못/별로/전혀`, 뒤에 `지 않/지 마` 있으면 해당 등장 **제외**(뒤집지 않음). canonical 기준 합산 → 주차·사람별 pos/neg top3. `count<3` 숨김
  5. 리허설 후 사전 덤프 → 윤아 검수 → 시드에 교정 반영
  - 남는 한계(발표 멘트): 반어·문맥 의존 표현은 못 잡음. 단어 단위 집계임을 명시
  - **시점: 지금.** Phase 2 = 토크나이즈(`Message.tokens`)·`weekly_terms`·공용 시드 사전 카운트·계약·리포트 카드 (결정론, 동기). Phase 3 초반 = `build_lexicon` 잡(LLM 분류+canonical) → `couple_lexicon` 갱신 → 재카운트. 처음부터 (b) 구조로 설계해 버리는 것 없음. **전제**: A4 재배분, B1·B2 Day 1 결정.
  - **미결**: 표시 단위(사람별 vs 합산) → B1에서

### A2. [x] 말 건 비율(`initiation_ratio`) 제거
- **문제**: 30분 경계에 따라 개시자가 뒤집히고, 사진 1장도 "말 걸기"로 세며, a/b 비교 프레임이라 P-1과 긴장. 로직이 약함에 동의.
- **선택지**: 제거 / 유지 / 표시만 빼고 내부 계산 유지
- **영향** (제거 시): `metrics.py` `_trend_metrics`·`_observe.init`, `API_SPEC` §4.1/4.2/5.1, `models/api.py`, `types.ts`, `REQUIREMENTS` FR-002 지표 표, `TEST_CASES` TC-METRIC-002, select 에이전트 후보 키. 세션 분할 자체는 유지(답장 시간·이상치·인용 단위).
- **결정**: **완전 제거.** 시간 간격으로 "대화 시작"을 정의하는 것 자체가 부적합. 지표·계약·테스트·템플릿 풀에서 `initiation_ratio` 삭제. `Session.initiator`는 돌아보기 세션 목록 표시용(사실 표시)으로만 남김. 리포트 후보 지표는 5개 + 신규(감성 단어, 요일·시간대). → E 플랜 실행 시 함께 반영.

### A3. [x] 챗봇 횟수 질문 처리 ("사랑해 몇 번 썼어?")
- **문제**: 벡터 검색 상위 8개만 보고 답해 틀린 숫자를 말할 위험. 더 근본적으로, 처음 계획한 `count_term`도 감성 사전 등재어만 셀 수 있었고(“치킨”·“엄마”는 영원히 0건) `build_lexicon`(LLM) 뒤에 묶여 있었다 — 세는 데 LLM은 필요 없다.
- **결정**: **단어 세기를 감성 분석에서 완전히 분리.** `term_count` intent + `count_term` 툴 신설, LLM 0회(regex 선분기).
  - 저장: 미리 전체 단어를 평문 저장하지 않는다. 질문이 오면 그때 본문을 메모리에서 복호화해 세고 폐기, 결과 `{단어, 주, 횟수}`만 `term_count_cache`에 캐시. 업로드 시 해당 커플 캐시 DELETE
  - 노출: **커플 합산만.** 발화자별 횟수는 표시하지 않는 수준이 아니라 **계산·저장하지 않는다** — `term_count_cache`에 `sender` 컬럼이 없어 구조적으로 불가 (B1 "내 단어는 본인만"이 우회로 무너지는 것 차단). 사람을 지목해 물어도 합산 + 안내 문구
  - 인용 없음(P-4 예외): 인용 카드가 발화자를 드러내므로 숫자·주별 추이를 근거로 삼는다
  - 매칭: 완전일치 · 접두일치(사랑→사랑해) · 같은 canonical(조아→좋아)
  - 복호화 지점이 3곳 → 4곳으로 늘어난 것을 TRD §4.1에 명시
  - → 반영됨: `term_count_cache`, `services/term_search.py`, `tools/count_term.py`, `prompts/chat_intent.md`, `agents/chat_supervisor.py`, Intent 계약, API_SPEC §6.1·§8, REQUIREMENTS FR-006·P-3·P-5, TRD §4.1·§5.3, TC-API-008-11~17, TASKS 3-1b, `tests/test_term_search.py`

### A4. [ ] 담당 재배분
- **문제**: 윤석 17.5건(34%), Phase 2 `2-1→2-2`, `2-3→2-4` 직렬 + Phase 3 Supervisor 2개·큐까지 크리티컬 패스 전부 집중.
- **제안**: 2-1 auth → 시여 / 3-12 Qdrant 삭제 → 윤아 / 4-2 OpenShift 통합 테스트 → 해찬 / 4-5 Mock 백업 점검 → 형준. 결과: 윤석 14(27%), 시여 10, 윤아 11, 해찬 11, 형준 5.5
- **영향**: `TASKS.md` §5~7, §10
- **결정**:

### A5. [x] canonical 묶기 범위 (A1이 (b)/(c)일 때)
- **문제**: LLM 정규화가 철자 변형(`조아`→`좋아`)만 묶을지, 동의어(`고마워`/`감사`/`땡큐`)까지 묶을지.
- **선택지**: 변형만 / 동의어까지
- **영향**: `prompts/lexicon.md`, TC-METRIC-007 고정 케이스
- **결정**: **철자 변형만 묶음**(`조아`·`좋앙`→`좋아`). 동의어(`고마워`/`감사`/`땡큐`)는 분리 — 커플 고유 표현이 보이는 게 가치 있고, 동의어 묶기는 LLM 판단이 흔들려 재현성을 해침.

---

## B. 원칙 충돌 — 팀 동의 필요

### B1. [x] P-1(판정 금지) vs 사람별 감성 단어
- **문제**: "부정 단어 1위: 짜증 12회"를 a/b로 나눠 보이면 "누가 더 부정적"으로 읽힘. 사람별 분리는 이미 결정됨.
- **대응안**: P-1 문구를 "단어 사용 횟수 등 **사실의 사람별 표시**는 허용, 그에 대한 **평가·비교 문장**만 금지"로 좁힘. 해석·제안 에이전트 프롬프트(윤아 2-12)에 "sentiment 수치를 비교하는 문장 금지" 명시 — 플랜이 강제 못 하는 부분이라 프롬프트 검수 규칙표에 포함.
- **영향**: `REQUIREMENTS` §0 P-1, `prompts/interpret.md`·`suggest.md`, TC-AGENT
- **결정**: **"내 단어" 카드 — 사람별이되 본인에게만 표시.** 기능 목표가 자기 성찰(재미 + 스스로 피드백)이므로 둘을 나란히 보이지 않음. A는 A의 pos/neg top3만, B는 B의 것만.
  - P-1 **수정 불필요** (비교 프레임 없음). 앱은 숫자만, "줄이세요" 류 문장 없음
  - **P-3 예외 1줄** 추가: "자기 성찰 섹션(내 단어)은 본인에게만 표시". `weekly_terms`는 양쪽 저장, `GET /reports/{week}`·타임라인 응답은 요청자 것만 `sentiment.mine`으로 (상대 데이터 미전송)
  - 오분류는 자기 말이라 본인이 판단 → 문맥 검증 단계는 **전제 아님**, Phase 3 여유 시 옵션 (C6)
  - 영향 파일 정정: `REQUIREMENTS` P-3, `API_SPEC` §4.1/4.2 `sentiment.mine`, `routers/reports.py`·`timeline.py`(요청자 필터), 프롬프트 변경 없음

### B2. [x] P-5(원문 암호화) vs 평문 테이블
- **문제**: `weekly_terms`(+ A1(b)면 `couple_lexicon`)는 단어 평문 저장. "원문은 암호화"의 예외가 생김. 원문 복원은 불가하지만 애칭·감정 단어가 평문으로 남음.
- **대응안**: `init.sql` 머리 주석 + `REQUIREMENTS` P-5에 예외 명시. 해제 시 CASCADE 삭제 확인(TC-API-002).
- **영향**: `REQUIREMENTS` §0 P-5, `init.sql`, `TRD` §4.1
- **결정**: **(가) 예외로 명시.** P-5에 "단어 단위 집계 테이블(`weekly_terms`, `couple_lexicon`)은 평문 저장. 원문 복원 불가, 해제·탈퇴 시 CASCADE 삭제" 1줄. `init.sql` 머리 주석·`TRD` §4.1 복호화 지점 목록에 동일 문구. 단어 암호화(나)는 같은 앱에 키가 있어 실익 없고 집계 쿼리만 막아 기각. API 노출은 B1의 `sentiment.mine`으로 본인 것만 전송. TC-API-002(해제 시 삭제)에 두 테이블 확인 추가.

---

## C. 구현 단계 메모 — 담당자가 코드 쓸 때 (해찬 결정 아님, 전달용)

### C1. [ ] 리포트 생성 병렬화 (윤석)
- 현재 설계: 워커 1개, `for week in weeks` 순차, 주당 LLM 3회 → 25주 ≈ 10분+, 재시도 겹치면 20분. 두 번째 커플은 뒤에 줄 섬.
- 할 것: `Semaphore(3)`+`gather` 주차 병렬 / **최신 주부터** / 기준선 부족 첫 4주는 LLM 없이 즉시 `insufficient_baseline` / select+interpret 1회 호출 통합(코드가 이상치·delta 상위 3 선별 → select 에이전트 불필요. 윤아 2-12에 영향, Day 1 공유)
- 파일: `services/jobs.py`, `agents/report_supervisor.py`, `TRD` §4.3·§5.2

### C2. [ ] 업로드 동기 구간 이벤트 루프 점유 (윤석)
- 파싱·sha256·Fernet 18k건·INSERT가 동기 CPU → 잡 폴링·챗봇·`/health/ready` 정지, readiness probe 실패 가능.
- 할 것: `asyncio.to_thread(parse_and_compute)`, INSERT는 `executemany ... ON CONFLICT (couple_id, msg_hash) DO NOTHING`
- 파일: `routers/upload.py`, `services/postgres_service.py`

### C3. [ ] 인프로세스 큐 → DB 큐 (윤석)
- `asyncio.Queue` 워커가 예외로 죽으면 잡 영구 `running`, 롤아웃 시 유실.
- 할 것: `SELECT ... WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1` 2초 폴링, `while True: try/except`, 재시작 시 `running→queued` 리셋
- 파일: `services/jobs.py`, `main.py` lifespan, `TRD` §4.3

### C4. [ ] 챗봇 intent→답변 LLM 2회 순차 (윤석+윤아)
- p95 < 8s 목표가 빠듯. `advice_request`/`other`는 regex 사전 분기(TC-API-008-4~6 고정 문구), 나머지는 검색 먼저 후 `{intent, answer, citations}` 1회 호출
- 파일: `agents/chat_supervisor.py`, `prompts/chat_intent.md`, `TRD` §5.3

### C5. [ ] 재업로드 중복 해시 — PC/모바일 시각 형식 (윤석)
- PC 내보내기는 초, 모바일은 분 단위 → 같은 메시지 해시가 달라 겹치는 구간이 2배 저장될 수 있음. 이름 매핑 후 해시인지도 확인.
- 할 것: 파서에서 `sent_at`을 분 단위로 정규화하고 해시에는 `a/b` 매핑된 sender 사용. TC-API-003에 "PC 업로드 후 iOS 동일 구간 재업로드 → new_messages 0" 케이스 추가
- 파일: `services/kakao_parser.py`, `routers/upload.py`, `TEST_CASES` TC-API-003

### C6. [ ] (옵션) 감성 단어 문맥 검증 단계 (윤석, Phase 3 여유 시)
- 표시 후보(주차·사람별 pos/neg 상위 5)의 등장 건마다 앞뒤 메시지 1~2개를 붙여 LLM이 keep/drop → 코드 재카운트. 반어·부정어까지 잡힘.
- 비용: 첫 소급 ~10만 토큰(1회), 이후 주당 ~4천. 판정은 `term_verdict(msg_hash, term, keep)`에 영구 저장(재현성). P-2에 "LLM은 제외 라벨만, 합산은 코드, 라벨은 메시지당 1회 고정" 예외 문구 필요.
- B1이 "본인에게만 표시"라 전제 조건 아님. 리허설에서 오분류가 거슬리면 투입.

---

## D. 과설계 제거 후보

### D1. [x] CronJob `/internal/weekly` (해찬)
- 카톡 연동이 없어 새 데이터는 업로드로만 들어오고 업로드가 이미 잡을 큐에 넣음 → 크론은 할 일 없음. 엔드포인트도 API_SPEC에 없음.
- 선택지: 제거 / NFR-006 요건이면 `pending|failed` 주만 재큐하는 멱등 엔드포인트로 축소
- 파일: `openshift/40-report-cronjob.yaml`, `TRD` §1.1·§8.1, TASKS 3-11
- **결정**: **제거.** 교육 자료에 CronJob 없음(실습 범위: Deployment/StatefulSet/Route/Secret/Tekton) → 기획 때 추가된 항목. `openshift/40-report-cronjob.yaml` 삭제, `REQUIREMENTS` NFR-006에서 "CronJob" 삭제, `TRD` §1.1 그림·§8.1 40번 행·§9 대응표 정리, TASKS 3-11 삭제. "주 1회 자동 리포트"는 REQUIREMENTS 로드맵(FR-007~009 옆)에 1줄 — 주기적 데이터 유입이 생기면 그때.

### D2. [x] 컬렉션 B(지식·템플릿)를 Qdrant에 (윤아)
- `(metric, direction)` 조합 ~12개 → 벡터 검색 불필요. 시드 스크립트·시작 시 임베딩·차원 문제만 얹음.
- 선택지: 메모리 dict `{(metric, direction): [...]}`로 앱 시작 시 로드 / 유지
- 파일: `TRD` §4.2, `scripts/seed_knowledge.py`, `SEED_KNOWLEDGE_ON_START`, TASKS 3-2
- **결정**: **메모리 dict.** `data/knowledge/*.md`·`templates.json`을 `container.py`에서 앱 시작 시 `{(metric, direction): [...]}`로 로드. `search_knowledge`·`get_suggestion_templates`는 dict 조회(시그니처 유지, `query`는 무시). 삭제: `scripts/seed_knowledge.py`, `.env.example`/`config.py`의 `SEED_KNOWLEDGE_ON_START`·`QDRANT_COLLECTION_KNOWLEDGE`, `qdrant_service.ensure_collections`의 컬렉션 B, `TRD` §4.2 컬렉션 B 행. TASKS 3-2는 "문서·템플릿 작성"만 남김(적재 없음). Qdrant는 컬렉션 A만. 자유 질의 검색이 필요해지면 그때 재도입.

### D3. [ ] Instana/OTel (해찬)
- 클러스터에 agent DaemonSet 없으면 전부 헛일. 1-V5 결과 후 결정. 없으면 `execution_trace` JSONB만 남김.
- **결정** (1-V5 후):

### D4. [→] `ReviewMetrics.range/baseline: dict[str, Any]` (윤석+시여)
- 돌아보기 화면(가장 늦게 확정)에 타입이 없어 프론트·백이 각자 추측. Phase 3 전까지 `WeekSummary` 서브셋 모델로 고정.
- 파일: `models/api.py`, `types.ts`, `API_SPEC` §5.1
- **담당자 판단 (해찬 결정 아님)**: 시여·윤석이 Phase 3 시작 전 30분 맞추면 됨. 기준은 API_SPEC §5.1 예시 JSON (A2 반영해 `initiation_ratio` 제거된 상태여야 함). 타입으로 박을지는 두 사람이 결정.

---

## E. 구조 수정 플랜 — 반영 완료 (2026-08-23)

| # | 항목 | 반영 |
|---|---|---|
| 1 | 세션 ID 결정론화 | `init.sql` PK `(couple_id, session_id)`, `metrics.split_sessions` epoch 초, API_SPEC·TRD |
| 2 | 임베딩 잡 분리 | `jobs.kind embed_sessions`, `UploadResponse.embed_job`, `JobResponse.kind`, API_SPEC §3.1 규칙 9 |
| 3 | 변경 주차 정의 | `weekly_metrics.summary_hash`, API_SPEC 규칙 8, REQUIREMENTS FR-002 #8 |
| 4 | 인덱스 | `idx_messages_session`, `idx_couples_user_a/b` |
| 5 | `active_job` 계약 | `CoupleMeResponse.active_job`, API_SPEC §2.4, mock |
| 6 | Qdrant 차원 검증 | `qdrant_service.ensure_collections` 재생성 |
| 7 | `initiation_ratio` 제거 (A2) | metrics·계약·mock·REQUIREMENTS·TEST_CASES·TASKS 2-11 |
| 8 | 활발한 요일·시간대 | `summary.activity`, `Activity` 모델, TC-METRIC-006 |
| 9 | "내 단어" 카드 (A1·A5·B1·B2) | `couple_lexicon`·`weekly_terms`, `Message.tokens`·`tokenize`, `count_terms`·`top_terms`, `sentiment_seed.json`, `MyTerms` 본인만, P-3·P-5 예외, `prompts/lexicon.md`, `chat_intent.md` 횟수→other (A3), TC-METRIC-007 |
| 10 | 질문 판정 개선 | `is_question` 4규칙, `tests/test_parser.py` 21케이스, TC-PARSE-004 |
| 11 | CronJob 제거 (D1) | `openshift/40-*` 삭제, NFR-006, TRD, TASKS 3-11 |
| 12 | 컬렉션 B 메모리화 (D2) | `services/knowledge.py`, `container.knowledge`, `seed_knowledge.py`·`SEED_KNOWLEDGE_ON_START` 삭제 |
| 13 | TASKS 그래프·메모 | 빌드 의존성만, 2-0 jobs 인프라, C1~C6·D4 메모를 행 비고에 |

## 남은 것
- **A4** 담당 재배분 — 팀 회의 후 TASKS §5~7·§10 수정
- **D3** Instana — 1-V5 후
- **C1~C6, D4** — TASKS 비고로 이관됨. 담당자가 구현 시 적용. 이 파일에선 추적 안 함
