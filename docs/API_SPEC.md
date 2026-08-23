# 커플 대화 리포트 — API 명세서 (API_SPEC.md)

> 상태: **계약 초안 v0.1** — 프론트·백엔드 동시 착수용. 첫날 실측(V1~V6) 후 개정.
> 기준 문서: 기획서 v1 §5·§7, REQUIREMENTS.md, DATA_MODEL.md

## 공통 규칙

### 인증

- 모든 `/api/*` 요청은 `Authorization: Bearer <token>` 필수 (`/api/auth/*` 제외)
- 토큰은 `user_id`를 담는다. 커플 범위 리소스는 토큰의 user가 해당 `couple_id`의 구성원인지 서버가 검증한다
- MVP에서는 간단한 JWT. 해커톤 데모용으로 이메일+비밀번호만.

### 에러 응답 형식

```json
{ "error": { "code": "ERROR_CODE", "message": "사람이 읽을 수 있는 메시지" } }
```

### HTTP 상태 코드

| 코드 | 의미 | 사용 |
|---|---|---|
| 200 | OK | 조회·수정 성공 |
| 201 | Created | 생성 성공 |
| 202 | Accepted | 비동기 작업 접수 (업로드 → 리포트 소급 생성) |
| 204 | No Content | 삭제 성공 |
| 400 | Bad Request | 요청 검증 실패 |
| 401 | Unauthorized | 토큰 없음/만료 |
| 403 | Forbidden | 다른 커플 리소스 접근 |
| 404 | Not Found | 리소스 없음 |
| 409 | Conflict | 상태 충돌 (이미 연결된 커플, 이미 처리된 초대 등) |
| 422 | Unprocessable | 파일은 받았으나 처리 불가 (형식 미지원, 발화자 2명 아님) |
| 500 | Internal Server Error | 서버 오류 |
| 503 | Service Unavailable | watsonx 호출 실패 (Mock 모드 fallback 가능) |

### 에러 코드

| 코드 | 상태 | 의미 |
|---|---|---|
| VALIDATION_ERROR | 400 | 요청 데이터 검증 실패 |
| UNAUTHORIZED | 401 | 인증 실패 |
| NOT_COUPLE_MEMBER | 403 | 해당 커플 구성원 아님 |
| COUPLE_NOT_ACTIVE | 403 | 커플 상태가 active 아님 (연결 미완료) |
| NOT_FOUND | 404 | 리소스 없음 |
| INVITE_INVALID | 404 | 초대 코드 없음/만료 |
| ALREADY_COUPLED | 409 | 이미 다른 커플에 속함 |
| INVITE_SELF | 409 | 자기 자신의 초대 코드 입력 |
| INVITE_STATE | 409 | 초대 상태가 요청과 맞지 않음 |
| UNSUPPORTED_FORMAT | 422 | 카톡 내보내기 형식 인식 실패 |
| NOT_COUPLE_CHAT | 422 | 발화자가 2명이 아님 |
| NAME_MAPPING_REQUIRED | 422 | 카톡 이름 → A/B 매핑 미지정 |
| INSUFFICIENT_DATA | 200 | (에러 아님) 기준선 부족 — 응답 본문 `status`로 표현 |
| LLM_UNAVAILABLE | 503 | watsonx 호출 실패 |

### 날짜·시각

| 종류 | 형식 | 예 |
|---|---|---|
| 주 시작일 | `YYYY-MM-DD` (월요일) | `2026-08-17` |
| 시각 | ISO 8601, tz 포함 (KST) | `2026-08-19T23:41:00+09:00` |

### 발화자 식별

API 응답에서 발화자는 항상 `"a"` / `"b"`. 실제 이름은 `GET /api/couples/me`의 `members`로 매핑한다. 리포트·챗봇 본문도 `"a"`/`"b"` 대신 `display_name`을 치환해 렌더하는 건 프론트 책임.

### 세션 식별

`session_id` = 세션 첫 메시지 시각의 **epoch 초** (결정론). 재업로드로 세션을 다시 나눠도 같은 세션은 같은 ID라서 리포트 발췌·메모·챗봇 인용·Qdrant 포인트 참조가 유지된다.

---

## 1. 인증

### 1.1 POST /api/auth/signup

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| email | string | O | 이메일 형식, unique |
| password | string | O | 8자 이상 |
| display_name | string | O | 1~20자 |

**Response 201**
```json
{ "user_id": "uuid", "token": "jwt" }
```
**에러**: VALIDATION_ERROR, 409 `EMAIL_TAKEN`

### 1.2 POST /api/auth/login

| 필드 | 타입 | 필수 |
|---|---|---|
| email | string | O |
| password | string | O |

**Response 200**: `{ "user_id", "token" }` · **에러**: 401 UNAUTHORIZED

---

## 2. 커플 연결 (FR-001)

상태 전이: `pending`(코드 발급) → `awaiting_confirm`(B 입력) → `active`(A 수락) → `dissolved`

### 2.1 POST /api/couples/invite

초대 코드 생성. 호출자가 A가 된다.

**처리 규칙**
- 호출자가 이미 `active`/`awaiting_confirm` 커플에 속하면 409 ALREADY_COUPLED
- 기존 `pending` 코드가 있으면 새로 발급하지 않고 같은 코드 반환
- 코드: 영대문자+숫자 8자, 7일 만료

**Response 201**
```json
{ "couple_id": "uuid", "invite_code": "K7P2M9QX", "expires_at": "2026-08-29T00:00:00+09:00", "status": "pending" }
```

### 2.2 POST /api/couples/join

| 필드 | 타입 | 필수 |
|---|---|---|
| invite_code | string | O |

**처리 규칙**
- 호출자가 이미 커플에 속하면 409 ALREADY_COUPLED
- 자기 코드면 409 INVITE_SELF
- 코드 없음/만료 → 404 INVITE_INVALID
- 상태가 `pending`이 아니면 409 INVITE_STATE
- 성공 시 `user_b` 설정, 상태 → `awaiting_confirm`

**Response 200**
```json
{ "couple_id": "uuid", "status": "awaiting_confirm", "partner": { "display_name": "형준" } }
```

### 2.3 POST /api/couples/{couple_id}/confirm

A가 연결을 수락/거절. **상호 동의의 마지막 단계.**

| 필드 | 타입 | 필수 |
|---|---|---|
| accept | boolean | O |

**처리 규칙**
- 호출자가 `user_a`가 아니면 403
- 상태가 `awaiting_confirm`이 아니면 409 INVITE_STATE
- `accept=true` → `active`, `accept=false` → `user_b` 해제, 상태 `pending`(코드 재사용 가능)

**Response 200**: `{ "couple_id", "status": "active" | "pending" }`

### 2.4 GET /api/couples/me

**Response 200**
```json
{
  "couple_id": "uuid",
  "status": "active",
  "members": { "a": { "user_id": "uuid", "display_name": "형준" }, "b": { "user_id": "uuid", "display_name": "윤아" } },
  "me": "a",
  "kakao_names": { "a": "김형준", "b": "윤아♥" },
  "started_at": "2026-03-01",
  "data": { "first_week": "2026-03-02", "last_week": "2026-08-17", "weeks_available": 25, "message_count": 18342 },
  "active_job": { "job_id": "uuid", "kind": "report_backfill", "done": 12, "total": 25 }
}
```
커플 없으면 200 `{ "couple_id": null, "status": null }` (404 아님 — 온보딩 분기용).
`active_job`: `queued|running` 인 최신 잡 1건, 없으면 `null` — 새로고침 후 진행률 UI 복구용 (프론트는 이게 있을 때만 `GET /jobs/{id}` 폴링).

### 2.5 DELETE /api/couples/{couple_id}

커플 해제 + **모든 대화·지표·리포트·메모 즉시 삭제** (Postgres CASCADE + Qdrant `couple_id` 필터 삭제). 어느 쪽이든 호출 가능.

**Response 204**

---

## 3. 대화 업로드 (FR-002)

### 3.1 POST /api/couples/{couple_id}/upload

`multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| file | file | O | `.txt` 또는 `.zip`(iOS 도큐멘트). 최대 50MB |
| name_map | JSON string | X | `{"a": "김형준", "b": "윤아♥"}`. 최초 업로드 시 필수, 이후 생략 가능 |

**처리 규칙**
1. 커플 상태 `active` 아니면 403 COUPLE_NOT_ACTIVE
2. zip이면 내부 `.txt` 추출, 나머지 폐기
3. 형식 감지 실패 → 422 UNSUPPORTED_FORMAT
4. 발화자 ≠ 2명 → 422 NOT_COUPLE_CHAT (`detail.senders`에 발견된 이름 목록)
5. `name_map` 없고 `couples.kakao_name_*`도 없으면 422 NAME_MAPPING_REQUIRED (`detail.senders` 포함 → 프론트가 매핑 UI 표시)
6. 메시지 해시로 중복 제거, 신규만 insert
7. **동기**: 세션 분할 → 전 주차 지표 계산 → `weekly_metrics` upsert (`summary_hash` = sha256(summary JSON)) → `weekly_terms` 집계(시드 사전 + `couple_lexicon`)
8. **비동기 (리포트)**: `summary_hash`가 바뀐 주차만 리포트 재생성 큐(`report_backfill`) → `job_id` 반환. 리포트에 저장된 baseline은 **생성 시점 스냅샷** — 하류 주차는 자동 재생성하지 않음 (필요 시 §4.3 regenerate)
9. **비동기 (임베딩)**: Qdrant 적재는 별도 `embed_sessions` 잡(`embed_job.job_id`)으로 리포트 잡보다 **먼저** 실행. 신규·변경 세션만 upsert (point id `{session_id}:{chunk_idx}`, 멱등) → 챗봇은 리포트 완성 전에도 동작
10. **비동기 (사전, Phase 3)**: `build_lexicon` 잡 — 커플 빈도 상위 단어 중 미분류분을 LLM 이 분류(철자 변형 canonical·pos/neg/neutral/exclude) → `couple_lexicon` append → 영향 주차 `weekly_terms` 재집계

**Response 202**
```json
{
  "job_id": "uuid",
  "embed_job": { "job_id": "uuid" },
  "parsed": { "format": "ios", "message_count": 18342, "new_messages": 412, "session_count": 1203, "range": { "from": "2026-03-02", "to": "2026-08-21" } },
  "weeks_computed": 25,
  "report_jobs": { "total": 25, "pending": 25 }
}
```

**에러 detail 예**
```json
{ "error": { "code": "NAME_MAPPING_REQUIRED", "message": "대화 참여자를 A/B에 연결해주세요", "detail": { "senders": ["김형준", "윤아♥"] } } }
```

### 3.2 GET /api/jobs/{job_id}

**Response 200**
```json
{ "job_id": "uuid", "kind": "embed_sessions" | "build_lexicon" | "report_backfill" | "report_single", "status": "running" | "done" | "failed", "progress": { "total": 25, "done": 12, "failed": 0 }, "current_week": "2026-05-18" }
```

---

## 4. 타임라인·리포트 (FR-003, FR-004)

### 4.1 GET /api/couples/{couple_id}/timeline

전 주차 지표 요약. 타임라인 그래프용. 리포트 본문 없음.

**Query**: `from`, `to` (YYYY-MM-DD, 선택)

**Response 200**
```json
{
  "weeks": [
    {
      "week_start": "2026-08-17",
      "in_progress": false,
      "report_status": "generated" | "insufficient_baseline" | "pending" | "failed",
      "summary": {
        "session_count": 18, "message_count": 412,
        "question_rate": { "a": 0.18, "b": 0.22 },
        "message_length_median": { "a": 14, "b": 11 },
        "reply_gap_median_min": { "a": 4, "b": 6 },
        "resume_delay_median_min": { "a": 95, "b": 140 },
        "session_length_median": 22,
        "activity": { "top_weekday": 2, "top_hour": 21, "by_weekday": [48, 55, 81, 60, 52, 70, 46], "by_hour": [2, 1, 0, "…(24)"] },
        "sentiment": { "pos": [{ "canonical": "좋아", "count": 41 }, { "canonical": "고마워", "count": 12 }], "neg": [{ "canonical": "피곤", "count": 7 }] }
      },
      "outlier_count": 2,
      "events": []
    }
  ]
}
```
- `activity`: 커플 합산 요일(0=월)·시간대(0~23) 메시지 수. 메시지 없으면 `top_*` null
- `sentiment` **"내 단어"**: **요청자 본인**의 긍정/부정 단어 상위 3 (`count < 3` 숨김). 상대 데이터는 전송하지 않는다 (P-3 예외). 사전 미구축이면 `null`. 단어 단위 집계라 반어·문맥은 반영 안 됨

### 4.2 GET /api/couples/{couple_id}/reports/{week_start}

**처리 규칙**
- `week_start`가 월요일 아니면 400
- 해당 주 데이터 없으면 404
- 리포트 생성 전이면 200 + `status: "pending"` + `summary`만

**Response 200** — 기획서 §7.2 구조 그대로
```json
{
  "week_start": "2026-08-17",
  "status": "generated",
  "summary": { "...": "4.1과 동일" },
  "metrics": {
    "question_rate": { "...": "..." },
    "message_length_median": { "...": "..." }
  },
  "highlights": [
    {
      "id": "h1", "metric": "question_rate", "who": "a",
      "observation": "지난 4주 대비 A가 묻는 질문이 28% 줄었어요.",
      "interpretations": ["바쁜 시기였을 수 있어요.", "대화 주제가 일상 공유 쪽으로 바뀌었을 수 있어요."],
      "evidence": [{ "session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?" }],
      "sources": [{ "doc": "communication_basics.md", "section": "관심 표현으로서의 질문" }],
      "sentiment": "neutral"
    }
  ],
  "suggestions": [
    { "id": "s1", "linked_highlight": "h1", "template_id": "q_rate_down_01", "text": "궁금하다면 이번 주에 하나 시도해볼 수 있어요: 상대 하루에 대해 질문 하나 더 던져보기." }
  ],
  "moments": [
    { "kind": "reply_gap_high", "who": "b", "at": "2026-08-19T23:41:00+09:00", "session_id": 1187, "value_min": 184, "baseline_median_min": 5, "text": "화요일 밤, B의 답장이 평소(5분)보다 긴 3시간이었어요." }
  ],
  "safety": { "passed": true, "rewritten": [] }
}
```

**불변 규칙 (서버가 보장)**
- `interpretations.length >= 2`
- `sentiment ∈ {positive, neutral, notable}`
- `suggestions[].template_id`는 지식 dict(`data/knowledge/templates.json`)에 존재
- `status == "insufficient_baseline"`이면 `highlights`·`suggestions`는 `[]`, `metrics.*.comparable == false`

### 4.3 POST /api/couples/{couple_id}/reports/{week_start}/regenerate

리포트 재생성 (디버그·데모용). **Response 202** `{ "job_id" }`

---

## 5. 이 구간 돌아보기 (FR-005)

### 5.1 GET /api/couples/{couple_id}/review

**Query**
| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| start | ISO 8601 | O | 구간 시작 |
| end | ISO 8601 | O | 구간 끝 (최대 14일) |
| session_id | int | X | 주면 start/end 무시하고 해당 세션 |

**Response 200**
```json
{
  "range": { "start": "...", "end": "..." },
  "sessions": [{ "session_id": 1187, "started_at": "...", "ended_at": "...", "initiator": "a", "msg_count": 34 }],
  "metrics": {
    "range": { "question_rate": { "a": 0.1, "b": 0.3 }, "message_length_median": { "a": 9, "b": 20 }, "reply_gap_median_min": { "a": 3, "b": 41 }, "session_length_median": 34 },
    "baseline": { "weeks": 8, "question_rate": { "a": 0.22, "b": 0.24 }, "message_length_median": { "a": 14, "b": 12 }, "reply_gap_median_min": { "a": 4, "b": 6 }, "session_length_median": 22 }
  },
  "notes": [{ "note_id": 7, "author": "a", "body": "시험 끝나고 싸움", "created_at": "..." }]
}
```

### 5.2 POST /api/couples/{couple_id}/notes

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| range_start | ISO 8601 | O | |
| range_end | ISO 8601 | O | >= range_start |
| body | string | O | 1~500자 |

**Response 201**: `{ "note_id", "author": "a", "body", "range_start", "range_end", "created_at" }`

### 5.3 DELETE /api/couples/{couple_id}/notes/{note_id}

작성자만. **Response 204**

---

## 6. 대화 검색 챗봇 (FR-006)

### 6.1 POST /api/couples/{couple_id}/chat

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| message | string | O | 1~500자 |
| focus_range | object | X | `{ start, end }` — 돌아보기 화면에서 호출 시 구간 힌트 |
| history | array | X | 직전 대화 최대 6턴 `[{ role, content }]` |

**처리 규칙**
1. Supervisor가 intent 분류: `fact_query` / `metric_query` / `report_query` / `advice_request` / `other`
2. `fact_query` → 컬렉션 A 검색(couple_id 필터 + focus_range 가중) → 인용 포함 답변
3. `metric_query` → `get_metrics` 툴 → 수치 답변
4. `report_query` → `get_report` 툴 → 과거 리포트 내용 답변
5. `advice_request` → 검색 없이 **고정 리다이렉트 문구**, `answer: null`
6. `other` → "대화 기록·지표·리포트에 대해 물어봐 주세요". **횟수·빈도 질문("사랑해 몇 번 썼어?")도 `other`** — 현재 구조로는 정확히 셀 수 없어 "횟수는 아직 세어드릴 수 없어요"로 안내 (Phase 3 `count_term` 툴 후 `term_count` intent 로 교체)
7. 답변에 인용이 하나도 없으면 서버가 `answer`를 버리고 `"관련 기록을 찾지 못했어요"`로 대체 (근거 없는 말 금지)

**Response 200**
```json
{
  "intent": "fact_query",
  "answer": "2026년 3월 14일 저녁 대화에서 A가 처음 '자기야'라고 불렀어요.",
  "citations": [{ "session_id": 812, "at": "2026-03-14T19:22:00+09:00", "sender": "a", "snippet": "자기야 뭐해" }],
  "redirect": null,
  "trace_id": "uuid"
}
```

**advice_request**
```json
{ "intent": "advice_request", "answer": null, "citations": [], "redirect": "이 챗봇은 대화 기록을 찾아주는 도구예요. 관계에 대한 관점은 주간 리포트를 참고해 주세요.", "trace_id": "uuid" }
```

**에러**: 503 LLM_UNAVAILABLE (Mock 모드면 고정 응답 반환)

---

## 7. 시스템

### 7.1 GET /health/live → 200 `{ "status": "ok" }`
### 7.2 GET /health/ready → 200 `{ "postgres": true, "qdrant": true, "watsonx": true | "mock" }` / 503

---

## 8. 내부 툴 (Supervisor → 에이전트, 외부 미노출)

| 툴 | 시그니처 | 설명 |
|---|---|---|
| `search_conversation` | `(couple_id, query, start?, end?, k=8) → [{session_id, at, sender, snippet, score}]` | 컬렉션 A 벡터 검색 + 메타 필터 |
| `get_metrics` | `(couple_id, week_start? \| range?) → summary + metrics` | Postgres 조회 |
| `get_report` | `(couple_id, week_start) → report` | Postgres 조회 |
| `search_knowledge` | `(metric, direction, k=5) → [{doc, section, text, source}]` | 지식 dict (`data/knowledge/interpretations`, 메모리) |
| `get_suggestion_templates` | `(metric, direction) → [{template_id, text}]` | 지식 dict (`data/knowledge/templates.json`, 메모리) |
| `count_term` (Phase 3) | `(couple_id, term, start?, end?) → {count, by_week: [{week_start, count}]}` | `couple_lexicon` canonical → `weekly_terms` SUM. `build_lexicon` 잡 이후 |

---

## 9. 엔드포인트 ↔ FR 매핑

| 엔드포인트 | FR |
|---|---|
| /api/auth/* | FR-000 |
| /api/couples/invite, join, confirm, me, DELETE | FR-001 |
| /api/couples/{id}/upload, /api/jobs/{id} | FR-002 |
| /api/couples/{id}/timeline | FR-003 |
| /api/couples/{id}/reports/{week} | FR-004 |
| /api/couples/{id}/review, notes | FR-005 |
| /api/couples/{id}/chat | FR-006 |
