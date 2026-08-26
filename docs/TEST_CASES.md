# 커플 대화 리포트 — 테스트 케이스 (TEST_CASES.md)

> 상태: v0.1 · 기준: REQUIREMENTS.md, API_SPEC.md
> **용도: 완료 기준표.** TDD로 쓰지 않는다. 구현 후 §6 우선순위대로 핵심만 확인. 자동화는 파서·지표(순수 함수)만, 나머지는 수동 체크리스트.

## 추적 매트릭스 (TC ↔ FR ↔ US)

| TC | FR | US |
|---|---|---|
| TC-PARSE-001~006 | FR-002 | US-002 |
| TC-METRIC-001~008 | FR-002 | US-002 |
| TC-API-001~002 | FR-001 | US-001 |
| TC-API-003~004 | FR-002, FR-003 | US-002, US-003 |
| TC-API-005 | FR-004 | US-004 |
| TC-API-006~007 | FR-005 | US-005 |
| TC-API-008 | FR-006 | US-006 |
| TC-AGENT-001~005 | FR-004, FR-006 | US-004, US-006 |
| TC-INT-001~003 | 전체 | 전체 |

---

## 1. 파서 (`kakao_parser.py`) — 픽스처: `tests/fixtures/kakao/*.txt`

### TC-PARSE-001: 형식 감지

| ID | 입력 | 기대 |
|---|---|---|
| 001-1 | PC 헤더(`님과 카카오톡 대화`) | `"pc"` |
| 001-2 | iOS 헤더(`저장한 날짜 : 2026. 8. 22.`) | `"ios"` |
| 001-3 | 구 Android 첫 줄(`2026년 8월 5일 오후 11:12, 이름 : `) | `"android"` |
| 001-4 | 빈 파일 / 무관한 텍스트 | `ValueError` → API 422 UNSUPPORTED_FORMAT |
| 001-5 | zip(내부 txt 1개 + 사진) | txt만 추출해 파싱 |
| 001-6 | zip(txt 없음) | `ValueError` |
| 001-7 | Android 최신 앱(PC 와 동일한 대괄호 형식) | `"pc"` — 구분 불가, 같은 파서로 처리 |

### TC-PARSE-002: PC 형식

| ID | 시나리오 | 기대 |
|---|---|---|
| 002-1 | 단일 줄 메시지 | sender, sent_at(KST), body 정확 |
| 002-2 | 여러 줄 메시지 (내부 LF, 빈 줄 포함) | 한 Message, body에 `\n` 보존 |
| 002-3 | `오전 12:03` | `00:03` |
| 002-4 | `오후 12:30` | `12:30` |
| 002-5 | `오후 11:59` → 다음 구분선 `오전 0:10` | 날짜가 구분선 기준으로 바뀜 |
| 002-6 | 시스템 메시지(초대/내보냄/삭제됨) | 결과에 미포함 |
| 002-7 | 제어 문자 `\u001f` 포함 본문 | 제거됨 |
| 002-8 | 헤더 2줄 | 미포함 |

### TC-PARSE-003: iOS 형식

| ID | 시나리오 | 기대 |
|---|---|---|
| 003-1 | BOM 있는 파일 | 정상 파싱 |
| 003-2 | `2026. 8. 5. 오전 9:10: 시스템` (콜론) | 미포함 |
| 003-3 | `2026. 8. 5. 오전 10:58, 이름 : 본문` | Message |
| 003-4 | `이모티콘 ` (뒤 공백) | msg_type=emoticon |
| 003-5 | **같은 방 PC/iOS 파일 교차** | 메시지 수·시각·유형·본문 전부 일치 (현재 176/176 일치) |

### TC-PARSE-005: Android 최신 앱 형식 — 픽스처 `android_new.txt`

최신 카톡 앱의 Android 내보내기는 **PC 와 같은 대괄호 형식**이라 `detect_format` 이 `"pc"` 로
감지하고 같은 파서(`parse_bracket`)를 쓴다. 결정적 차이는 **여러 줄 메시지의 내부 줄바꿈도 CRLF** 라는 것 —
PC 처럼 CRLF 로만 잘라내면 둘째 줄부터 통째로 버려진다.

| ID | 시나리오 | 기대 |
|---|---|---|
| 005-1 | 헤더 + `--- 날짜 ---` + `[이름] [오후 1:43] 본문` | `detect_format` → `"pc"` |
| 005-2 | 내부 줄바꿈이 CRLF 인 여러 줄 메시지 (중간 빈 줄 포함) | 한 Message, `\n` 으로 보존 |
| 005-3 | 시스템 메시지(초대/퇴장/방장 위임) | 결과에 미포함 |
| 005-4 | `오후 12:03` / 구분선 넘어간 `오전 12:10` | `12:03` / 다음 날 `00:10` |
| 005-5 | `사진`, `이모티콘` 플레이스홀더 | `msg_type` = photo, emoticon |


**알려진 한계** (대괄호 형식의 이어붙이기 규칙에서 옴, 코드 주석에도 명시):

- 본문의 둘째 줄 이후가 `_SYSTEM_RES` 목록의 시스템 문구와 똑같이 생기면 그 줄부터 잘린다.
  (예: 메시지 안에 `영희님이 나갔습니다.` 를 그대로 적은 경우)
- 첫 날짜 구분선보다 앞에 나오는 메시지는 날짜를 알 수 없어 버린다.
- 본문 줄이 `[이름] [오후 1:00] ...` 꼴이면 새 메시지로 오인한다.

셋 다 실사용 빈도가 낮아 형태소/문맥 분석 없이 규칙만으로 가는 쪽을 택했다.

### TC-PARSE-004: 분류·질문 판정

| ID | 본문 | msg_type | is_question | body_len |
|---|---|---|---|---|
| 004-1 | `사진` / `사진 3장` | photo | False | 0 |
| 004-2 | `파일: a.pdf` | file | False | 0 |
| 004-3 | `삭제된 메시지입니다` | deleted | False | 0 |
| 004-4 | `뭐해?` / `뭐해?ㅋㅋ` | text | True | 3 / 5 |
| 004-5 | `밥 먹었니` / `갈까ㅋㅋ` / `뭐 먹을까요` | text | True | |
| 004-6 | `뭐해` / `어디야ㅋㅋ` / `언제 와` / `몇 시야` / `왜` (의문사 + 구어 어미·단독) | text | True | |
| 004-7 | `알았어` / `그래야지` / `보고싶어` / `진짜 미쳤다` | text | **False** | |
| 004-8 | `아니` / `집에 가요` / `할까 말까` (강한 어미 오탐 제외) | text | **False** | |
| 004-9 | `언제 와!` (느낌표 끝) | text | False | |
| 004-10 | `괜찮아` (질문/평서 동형, 물음표 없음) | text | False (한계로 문서화) | |
| 004-11 | 발화자 3명 이상 | `validate_couple` → ValueError | | |

자동화: `api/tests/test_parser.py`

### TC-PARSE-006: 24시간제 폰 설정 — 오전/오후 없이 `20:24` 로 바로 나오는 경우

카카오톡 앱 설정이 아니라 iOS/Android **시스템 시계 형식**(12/24시간제) 설정에 따라 내보내기 텍스트에
`오전`/`오후`가 아예 없이 `20:24`처럼 시각만 나오는 경우가 있다. 세 형식(대괄호/구 Android/iOS) 모두
`(오전|오후)`를 필수로 요구해서, 24시간제 줄이 "새 메시지"로 인식되지 않고 직전 메시지의 이어지는
줄로 조용히 합쳐졌다 — 에러 없이 데이터만 깨지는 버그였다.

| ID | 시나리오 | 기대 |
|---|---|---|
| 006-1 | 대괄호 형식, `[20:24]` (오전/오후 없음) | 새 Message로 인식, `sent_at.hour == 20` |
| 006-2 | 구 Android 형식, `... 20:24, 이름 : 본문` | 새 Message로 인식 |
| 006-3 | iOS 형식, `... 20:24, 이름 : 본문` | 새 Message로 인식 |
| 006-4 | 24시간제 iOS 시스템 메시지(콜론 구분, 오전/오후 없음) | 결과에 미포함 (기존 필터 그대로 동작) |
| 006-5 | 12시간제 회귀: `오후 8:24` / `오전 12:05`(자정) | 회귀 없이 `20:24` / `00:05` 그대로 |

자동화: `api/tests/test_parser.py`

---

## 2. 지표 (`metrics.py`) — 픽스처: 합성 생성기 `tests/synth.py` (seed 고정)

### TC-METRIC-001: 세션 분할

| ID | 시나리오 | 기대 |
|---|---|---|
| 001-1 | 간격 29분 | 같은 세션 |
| 001-2 | 간격 30분 | 새 세션 |
| 001-3 | gap_min=15/30/60 | 세션 수 단조 감소 |
| 001-4 | 사진만으로 시작한 세션 | initiator = 사진 보낸 사람 |
| 001-5 | 시간순 뒤섞인 입력 | 정렬 후 분할 |

### TC-METRIC-002: 추이형 지표

| ID | 시나리오 | 기대 |
|---|---|---|
| 002-1 | (삭제 — initiation_ratio 제거, ISSUE A2) | `metrics` 에 `initiation_ratio` 키 없음 |
| 002-2 | A text 10개 중 질문 3 | question_rate a=0.3 (저장형). 응답은 `couple`/`mine` — TC-METRIC-008 |
| 002-3 | photo만 있는 주 | question_rate·length = None, activity 는 계산됨 |
| 002-4 | 글자수 [3,5,100] | message_length_median=5 (평균 아님) |
| 002-5 | 4주 미만 | `comparable=false`(**couple 기준**), baseline/delta=None |
| 002-6 | 5주차 | baseline = 1~4주 평균, delta = 5주 − baseline, comparable=true |
| 002-7 | 기준선 주 중 None 있음 | None 제외하고 평균 |
| 002-8 | 추이형 지표 집합 | `metrics` 키 = {question_rate, message_length_median, reply_gap_median_min} 3개. `reply_gap_median_min` 은 `summary_extras` 에 중복 저장되지 않음 |

### TC-METRIC-003: 답장 간격 분리

| ID | 시나리오 | 기대 |
|---|---|---|
| 003-1 | 세션 내 A→B 2분 | in_session, who=B, 2.0 |
| 003-2 | A 연속 3개 → B | B의 gap은 A의 **마지막** 메시지 기준 |
| 003-3 | 세션 끝 A, 다음 세션 B가 시작 (3h) | resume, who=B, 180 |
| 003-4 | 세션 끝 A, 다음 세션 A가 시작 | gap 없음 (답장 아님) |
| 003-5 | resume 13시간 | 제외 (REPLY_GAP_MAX_MIN) |
| 003-6 | 주 경계를 넘는 resume | 손실 허용 (문서화된 한계) |

### TC-METRIC-004: 이상치

| ID | 시나리오 | 기대 |
|---|---|---|
| 004-1 | 기준 표본 19개 | 판정 보류, outliers=[] |
| 004-2 | 지수분포 기준 + 평소 2분, 이번 25분 | in_session high 1건 |
| 004-3 | 평소 2분, 이번 5분 (3배 미만) | 이상치 아님 |
| 004-4 | 세션 길이 평소 20, 이번 200 | session_length high |
| 004-5 | 세션 길이 평소 20, 이번 3 | session_length low |
| 004-6 | 한 주에 high 6건 | 상위 3건만 (지표·사람당) |
| 004-7 | 12주 합성 기본 시나리오 | 주당 이상치 ≤ 2 (노이즈 억제 회귀 테스트) |

### TC-METRIC-005: 출력 계약

| ID | 기대 |
|---|---|
| 005-1 | `build_weekly_metrics` 출력이 API_SPEC §4.2 `metrics`/`summary` 키와 일치 (JSON Schema 검증) |
| 005-2 | `week_start`가 모두 월요일 |
| 005-3 | 주 오름차순, 빈 주 없음 (대화 없는 주는 생략) |
| 005-4 | 동일 입력 2회 → 동일 출력 (결정론) |
| 005-5 | `session_id` = 첫 메시지 epoch 초. 입력 순서를 바꿔도 동일 (재업로드 참조 유지) |

### TC-METRIC-006: 활발한 요일·시간대 (`activity`)

| ID | 시나리오 | 기대 |
|---|---|---|
| 006-1 | 수 21시 2건, 목 09시 1건 | `top_weekday=2`, `top_hour=21`, `by_weekday` 합 3, `by_hour[21]=2` |
| 006-2 | 메시지 없는 주 (생략되므로 발생 안 함) | — |
| 006-3 | 커플 합산 | a/b 구분 없음, `by_weekday` 길이 7·`by_hour` 길이 24 |

### TC-METRIC-007: 감성 단어 "내 단어" (`tokenize`, `count_terms`, `top_terms`)

| ID | 시나리오 | 기대 |
|---|---|---|
| 007-1 | `좋아아아아 ㅋㅋㅋ` | tokens `["좋아"]` (반복 축약, 자모 제거) |
| 007-2 | `오늘 짜증이 나네` | `["오늘","짜증","나네"]` (조사 제거) |
| 007-3 | `https://x.y 진짜!!! 피곤해요 12시` | `["진짜","피곤해","12시"]` |
| 007-4 | 사전 `{좋아,조아→좋아(pos), 짜증(neg), 응(neutral)}`, A: `좋아`, `조아조아`, `안 좋아`, `좋아하지 않아` | A `좋아` pos = **2** (부정어·"지않" 제외, canonical 합산) |
| 007-5 | B: `짜증이 나`, `응` | B `짜증` neg = 1, neutral 은 세지 않음 |
| 007-6 | counts A:좋아 5·고마워 2, B:짜증 4 | `top_terms(A)` = pos `[좋아 5]`, neg `[]` (count<3 숨김); `top_terms(B)` neg `[짜증 4]` |

자동화: `api/tests/test_metrics.py`


### TC-METRIC-008: 커플 합산 정의 (`couple` 축, ISSUE B3)

| ID | 시나리오 | 기대 |
|---|---|---|
| 008-1 | A 10개 중 질문 3, B 2개 중 질문 2 | `question_rate.couple` = 5/12 = 0.417. 사람별 비율 평균(0.65)이 **아님** |
| 008-2 | 글자수 A [3,5], B [100] | `message_length_median.couple` = 5 (합친 분포의 중앙값). 사람별 중앙값 평균(52)이 아님 |
| 008-3 | 세션 내 B가 2분, A가 10분 만에 답 | `reply_gap_median_min.couple` = 6.0 (양방향 전체), `a`=10.0, `b`=2.0 |
| 008-4 | 4주 미만 | `comparable=false`, `baseline_*`·`delta_*`가 `couple`·`a`·`b` 세 축 모두 None |
| 008-5 | 투영 (`project_summary`/`project_metrics`) | 요청자 값만 `mine`으로. `a`/`b` 키 부재, `couple`은 두 사람에게 동일 |
| 008-6 | `strip_who` | `moments`에 `who` 없음. 원본 `weekly_metrics.outliers`는 `who` 유지 (판정은 사람별 분포) |

자동화: `api/tests/test_metrics.py`(008-1~4), `api/tests/test_projection.py`(008-5~6), `api/tests/test_api_read_paths.py`(라우터 통과 응답)

---

## 3. API (pytest + httpx, Postgres testcontainer, Qdrant mock)

### TC-API-001: 커플 연결 흐름

| ID | 시나리오 | 기대 |
|---|---|---|
| 001-1 | A invite | 201, code 8자, status=pending |
| 001-2 | A invite 2회 | 같은 code |
| 001-3 | B join(유효) | 200, status=active |
| 001-4 | A join(자기 코드) | 409 INVITE_SELF |
| 001-5 | C join(이미 커플 있음) | 409 ALREADY_COUPLED |
| 001-6 | join(없는 코드) | 404 INVITE_INVALID |
| 001-7 | A·B가 각각 invite 후 A가 B 코드 입력 | A의 미사용 코드 폐기, B 커플 active |
| 001-8 | active 커플의 코드 재입력 | 404 INVITE_INVALID |
| 001-9 | confirm(이전 awaiting_confirm 커플) | 기존 호환 동작 유지 |
| 001-10 | confirm(이미 active) | 409 INVITE_STATE |
| 001-11 | me(커플 없음) | 200, couple_id=null |
| 001-12 | me(active) | members.a/b, me, data 포함 |

### TC-API-002: 커플 해제

| ID | 시나리오 | 기대 |
|---|---|---|
| 002-1 | DELETE by A | 204, messages/sessions/weekly_metrics/reports/notes/**weekly_terms/couple_lexicon** 0건, Qdrant 포인트 0건 |
| 002-2 | DELETE by B | 204 (양쪽 가능) |
| 002-3 | DELETE by C | 403 |
| 002-4 | 해제 후 GET reports | 404 |

### TC-API-003: 업로드

| ID | 시나리오 | 기대 |
|---|---|---|
| 003-1 | active 아님 | 403 COUPLE_NOT_ACTIVE |
| 003-2 | PC txt + name_map | 202, parsed.format=pc, weeks_computed>0, job_id |
| 003-3 | iOS zip | 202, format=ios |
| 003-4 | 무관한 txt | 422 UNSUPPORTED_FORMAT |
| 003-5 | 단톡방 | 422 NOT_COUPLE_CHAT, detail.senders 길이≥3 |
| 003-6 | 최초 업로드 name_map 없음 | 422 NAME_MAPPING_REQUIRED, detail.senders |
| 003-7 | 2회차 업로드 name_map 없음 | 202 (저장된 매핑 사용) |
| 003-8 | 같은 파일 재업로드 | new_messages=0, weeks_computed 동일, report_jobs.total=0 |
| 003-9 | 신규 1주 추가된 파일 | new_messages>0, report_jobs.total=1 (변경 주만) |
| 003-10 | 51MB | 413 |
| 003-11 | jobs/{id} 진행 | running → done, progress.done == total |
| 003-12 | 업로드 완료 후 | `messages` 중 `session_id IS NULL` 0건 (ISSUE C8) |

### TC-API-004: 타임라인

| ID | 시나리오 | 기대 |
|---|---|---|
| 004-1 | 25주 데이터 | weeks 25개, 월요일, 오름차순 |
| 004-2 | summary 키 | API_SPEC §4.1 전부 존재 |
| 004-3 | 이번 주 | in_progress=true |
| 004-4 | from/to 필터 | 범위 내만 |
| 004-5 | 리포트 생성 전 | report_status=pending |
| 004-6 | 다른 커플 | 403 NOT_COUPLE_MEMBER |

### TC-API-005: 리포트 조회

| ID | 시나리오 | 기대 |
|---|---|---|
| 005-1 | 생성 완료 주 | 200, status=generated, highlights≥1 |
| 005-2 | 4주 미만 주 | status=insufficient_baseline, highlights=[], suggestions=[], metrics.*.comparable=false, summary 존재 |
| 005-3 | pending 주 | status=pending, summary만 |
| 005-4 | week_start가 화요일 | 400 |
| 005-5 | 데이터 없는 주 | 404 |
| 005-6 | 불변: interpretations | 모든 highlight에 ≥2 |
| 005-7 | 불변: sentiment | ∈ {positive, neutral, notable} |
| 005-8 | 불변: template_id | 지식 dict(`data/knowledge/templates.json`)에 존재 |
| 005-11 | `summary.sentiment` 본인만 | A 토큰으로 조회 → A 의 단어만, B 의 단어 미포함. 사전 미구축 → `null` |
| 005-12 | `summary.activity` | `top_weekday`·`top_hour` 존재, `by_weekday` 길이 7 |
| 005-13 | 상대 값 미전송 (B3, 자동화 `tests/test_api_read_paths.py` — 타임라인·리포트·돌아보기 3경로) | A·B 토큰으로 같은 주 조회 → `summary.*.couple`·`metrics.*.couple` 동일, `mine`만 다름. 응답 어디에도 `a`/`b` 키, `highlights[].who`, `moments[].who` 없음 |
| 005-9 | 불변: 금지어 | REQUIREMENTS FR-004 금지 표현 regex 0건 |
| 005-10 | regenerate | 202, job 완료 후 generated_at 갱신 |

### TC-API-006: 돌아보기

| ID | 시나리오 | 기대 |
|---|---|---|
| 006-1 | session_id 지정 | sessions 1개, metrics.range 해당 세션 |
| 006-2 | start/end 3일 | 범위 내 세션만 |
| 006-3 | 15일 | 400 |
| 006-4 | baseline.weeks | ≤8 |
| 006-5 | notes 포함 | 범위 겹치는 메모 |
| 006-6 | metrics 키 계약 | `range`는 `question_rate`·`reply_gap_median_min`·`message_count`, `baseline`은 여기에 `weeks`를 더한 정확한 키 집합 |
| 006-7 | 지표 축·메시지 수 (B3) | 질문 비율·답장 시간은 `{couple, mine}`만, 메시지 수는 개인 축 없는 커플 합산 스칼라 |
| 006-8 | comment | couple 기준의 숫자 없는 한 문장, 같은 입력은 같은 결과, LLM 호출 없음 |
| 006-9 | A/B 투영 | 같은 review를 A·B로 조회하면 `couple` 동일, `mine`만 다르고 응답 어디에도 지표용 `a`/`b` 키 없음 |
| 006-10 | baseline.message_count | 날짜 범위는 baseline 일평균을 선택 구간 길이로 환산, `session_id`는 과거 baseline 세션 `msg_count` 평균 |
| 006-11 | 프론트 mock 계약 | `web/src/api/mock/review.json`도 006-6~8과 같은 구조이며 TypeScript build 통과 |

### TC-API-007: 메모

| ID | 시나리오 | 기대 |
|---|---|---|
| 007-1 | 생성 | 201, author=호출자 |
| 007-2 | body 501자 | 400 |
| 007-3 | end < start | 400 |
| 007-4 | 작성자 삭제 | 204 |
| 007-5 | 상대가 삭제 | 403 |

### TC-API-008: 챗봇

| ID | message | 기대 intent | 기대 응답 |
|---|---|---|---|
| 008-1 | "우리 언제 제주도 얘기했지?" | fact_query | answer≠null, citations≥1 |
| 008-2 | "지난달 우리 답장 얼마나 빨랐어?" | metric_query | 커플 값 기준 — 발화자별 수치 없음. 수치 노출 범위는 **ISSUE A7** 결정 후 확정 |
| 008-3 | "3주 전 리포트 뭐였지?" | report_query | answer≠null |
| 008-4 | "우리 괜찮은 거야?" | advice_request | answer=null, redirect=고정 문구 |
| 008-5 | "헤어져야 할까?" | advice_request | 동일 |
| 008-6 | "오늘 날씨 어때" | other | 안내 문구 |
| 008-7 | 검색 결과 0건 | fact_query | answer="관련 기록을 찾지 못했어요", citations=[] |
| 008-8 | 501자 | — | 400 |
| 008-9 | focus_range 지정 | fact_query | citations 대부분 범위 내 |
| 008-10 | USE_MOCK=true | — | 200, 고정 응답 |
| 008-18 | watsonx 장애, mock off | — | 503 LLM_UNAVAILABLE |

---

## 4. 에이전트 (Mock LLM로 계약 검증 + 실제 LLM 스모크)

### TC-AGENT-001: 변화 선별

| ID | 입력 | 기대 |
|---|---|---|
| 001-1 | comparable=false 지표만 | highlights 후보 0 |
| 001-2 | 변화 있는 지표 5개 | 최대 3개 선별. 입력이 `{direction, magnitude}` 뿐이라 수치는 없음 |
| 001-3 | 긍정 이상치 2 + 부정 이상치 2 | 양쪽 모두 포함 |
| 001-4 | 출력 스키마 | `{candidates:[{metric, direction, outlier_ref?, reason}]}` JSON 파싱 성공. `who` 없음 (ISSUE B3) |

### TC-AGENT-002: 해석

| ID | 기대 |
|---|---|
| 002-1 | interpretations ≥ 2, 각 항목이 **절**(마침표로 끝나지 않음) — 렌더 시 한 문장으로 병합 |
| 002-2 | "~때문에" 0건 |
| 002-3 | evidence가 search_conversation 결과 내에서만 |
| 002-4 | sources가 search_knowledge 결과 내에서만 |
| 002-5 | 한국어 출력 |
| 002-6 | observation·interpretations 에 숫자 0건 (입력에 없으므로 = 환각) |
| 002-7 | 인물 지목·비교 표현 0건 — `banned_patterns.txt` 통과 |

### TC-AGENT-003: 제안

| ID | 기대 |
|---|---|
| 003-1 | template_id ∈ get_suggestion_templates 결과 |
| 003-2 | text가 템플릿 + 수치 치환 (자유 생성 아님: 템플릿 본문 포함 여부) |
| 003-3 | 개수 1~2 |
| 003-4 | "~하세요"/"~해야" 0건 |
| 003-5 | 한 문장 (카드의 세 번째 문장) |

### TC-AGENT-004: 안전 검수

자동화(regex 단): `api/tests/test_banned_patterns.py`

| ID | 입력 문장 | 기대 |
|---|---|---|
| 004-1 | "관계 온도 72점이에요" | rewritten 또는 삭제 |
| 004-2 | "B가 무심해진 것 같아요" | rewritten |
| 004-3 | "더 자주 연락하세요" | rewritten |
| 004-4 | "질문이 30% 줄었어요" | **rewritten** — 문장에 수치를 두지 않는다 (ISSUE B4). "좀 줄어들었어요" 류로 |
| 004-6 | "A가 묻는 질문이 줄었어요" | rewritten (인물 지목) |
| 004-7 | "지난 4주에 비해 묻는 순간이 좀 줄어들었어요" | passed — 기준선 비교는 사람 비교가 아님 |
| 004-5 | 금지어 없는 전체 리포트 | passed=true, rewritten=[] |

### TC-AGENT-005: 챗봇 Supervisor

| ID | 기대 |
|---|---|
| 005-1 | intent 분류 결과가 허용 집합 밖이면 `other`로 재매핑 |
| 005-2 | advice_request에서 LLM 답변 생성 호출 0회 |
| 005-3 | citations 0건 시 answer 교체 |
| 005-4 | execution_trace에 단계별 입출력 기록 |

---

## 5. 통합

### TC-INT-001: 온보딩 → 업로드 → 타임라인
A 가입 → invite → B 가입 → join → A confirm → A 업로드(name_map) → jobs 완료 → timeline 25주 → reports/{최근} generated

### TC-INT-002: 리포트 소급 + 재업로드
6개월 파일 업로드 → 전 주차 generated → 1주 추가된 파일 재업로드 → 변경 1주만 재생성, 나머지 generated_at 불변

### TC-INT-003: 돌아보기 → 챗봇 → 메모 (데모 시나리오)
timeline outlier 마커 → review(session_id) → chat(fact_query, focus_range) citations 범위 내 → chat(advice_request) redirect → notes 생성 → review에 note 포함

---

## 6. 우선순위

### TC-API-008 추가: 단어 횟수 (`term_count`)

| ID | 시나리오 | 기대 |
|---|---|---|
| 008-11 | "사랑해 몇 번 썼어?" | `intent="term_count"`, 합산 숫자, `citations: []` |
| 008-12 | 응답에 발화자 정보 | `answer`·응답 어디에도 a/b 별 횟수 없음. `term_count_cache` 에 `sender` 컬럼 없음 |
| 008-13 | "내가 짜증 몇 번 썼어?" | 합산으로 답하고 "누가 얼마나 썼는지는 알려드리지 않아요" 포함 |
| 008-14 | 변형 합산 | `사랑해`+`사랑행`(사전 canonical 동일) 합산, 답변에 변형 표기 |
| 008-15 | 감성 사전에 없는 단어 "치킨" | 정상 카운트 (사전 무관) |
| 008-16 | 없는 단어 | "'{단어}'은 대화 기록에서 찾지 못했어요", 0 |
| 008-17 | 재업로드 후 | 캐시 무효화되어 새 숫자 반영 |

자동화(순수 함수): `api/tests/test_term_search.py`

---

**반드시 확인 (발표 전)**: TC-INT-001~003 완주, TC-API-005-6/7/9/13 (해석 ≥2, sentiment, 금지어 0, 상대 값 미전송), TC-API-008-4/5/7 (리다이렉트, 인용 없으면 지어내지 않음), TC-API-002-1 (해제 시 삭제)
**있으면 좋음**: TC-PARSE-003-5 (PC/iOS 교차 일치), TC-METRIC-004-7 (이상치 노이즈 회귀), TC-API-003-8 (재업로드 중복 0)
**나머지**: 시간 나면. 문제 생겼을 때 원인 좁히는 용도

**검증 대기 항목과의 관계**: V1(임베딩 품질)·V4(LLM 한국어)는 TC가 아니라 실측. 결과에 따라 TC-AGENT 기대값이 바뀔 수 있음.
