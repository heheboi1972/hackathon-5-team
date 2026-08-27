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

**Response 200**: `{ "user_id", "token", "couple_id?", "couple_status?" }`

- 활성 커플에 연결된 계정은 `couple_id`와 `couple_status: "active"`를 함께 반환한다.
- 연결되지 않은 계정은 두 커플 필드를 `null`로 반환한다.
- **에러**: 401 UNAUTHORIZED

---

## 2. 커플 연결 (FR-001)

상태 전이: `pending`(코드 발급) → `active`(상대방 코드 입력) → `dissolved`

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
- 호출자가 이미 `active`/`awaiting_confirm` 커플에 속하면 409 ALREADY_COUPLED
- 자기 코드면 409 INVITE_SELF
- 코드 없음/만료 → 404 INVITE_INVALID
- 상태가 `pending`이 아니면 409 INVITE_STATE
- 양쪽이 각각 코드를 발급한 경우, 코드를 입력한 쪽의 미사용 코드는 폐기한다
- 성공 시 `user_b` 설정, 상태 → `active` (추가 수락 없음)

**Response 200**
```json
{ "couple_id": "uuid", "status": "active", "partner": { "display_name": "형준" } }
```

### 2.3 POST /api/couples/{couple_id}/confirm

이전 수락 대기 연결을 자동 완료하는 호환용 API. 새 연결은 `join`에서 즉시 완료된다.

| 필드 | 타입 | 필수 |
|---|---|---|
| accept | boolean | O |

**처리 규칙**
- 호출자가 커플 구성원이 아니면 403
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
  "first_met_at": "2024-01-17",
  "data": { "first_week": "2026-03-02", "last_week": "2026-08-17", "weeks_available": 25, "message_count": 18342 },
  "active_job": { "job_id": "uuid", "kind": "report_backfill", "done": 12, "total": 25 }
}
```
커플 없으면 200 `{ "couple_id": null, "status": null }` (404 아님 — 온보딩 분기용).
`active_job`: `queued|running` 인 최신 잡 1건, 없으면 `null` — 새로고침 후 진행률 UI 복구용 (프론트는 이게 있을 때만 `GET /jobs/{id}` 폴링).

### 2.5 PATCH /api/couples/me

현재 로그인 사용자가 속한 커플의 설정을 수정한다. 요청에 `couple_id`를 포함하지 않는다.

**Request**
```json
{ "first_met_at": "2024-01-17" }
```

`first_met_at`은 `YYYY-MM-DD` 형식의 날짜 또는 `null`이다. `null`을 보내면 설정을 삭제한다.

**Response 200**: 수정된 `GET /api/couples/me`와 동일한 `CoupleMeResponse` 형식.

### 2.6 DELETE /api/couples/{couple_id}

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
        "question_rate": { "couple": 0.20, "mine": 0.18 },
        "message_length_median": { "couple": 12, "mine": 14 },
        "reply_gap_median_min": { "couple": 5, "mine": 4 },
        "resume_delay_median_min": { "couple": 118, "mine": 95 },
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
- 추이 지표 4개는 **`couple`(커플 합산) + `mine`(요청자 본인)**. 상대 값은 표시를 안 하는 수준이 아니라 **응답에 담지 않는다** (P-3 예외, ISSUE B3). 저장은 사람별로 하고 응답 조립 시점에 투영한다
- `couple`은 사람별 값의 평균이 아니라 두 사람 메시지를 **합친 뒤** 계산한 값(비율은 풀링, 중앙값은 합친 분포)
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
    "question_rate": {
      "couple": 0.20, "mine": 0.18,
      "baseline_couple": 0.245, "baseline_mine": 0.25,
      "delta_couple": -0.045, "delta_mine": -0.07,
      "comparable": true
    },
    "message_length_median": { "...": "동일 형태" },
    "reply_gap_median_min": { "...": "동일 형태" }
  },
  "highlights": [
    {
      "id": "h1", "metric": "question_rate",
      "observation": "지난 4주에 비해 서로에게 묻는 순간이 좀 줄어들었어요.",
      "interpretations": ["바쁜 시기였을 수도", "대화 주제가 일상 공유 쪽으로 옮겨간 걸 수도"],
      "evidence": [{ "session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?" }],
      "sources": [{ "doc": "communication_basics.md", "section": "관심 표현으로서의 질문" }],
      "sentiment": "neutral"
    }
  ],
  "suggestions": [
    { "id": "s1", "linked_highlight": "h1", "template_id": "q_rate_down_01", "text": "다음엔 상대 하루에 대해 질문 하나를 더 던져보면 어떨까요." }
  ],
  "moments": [
    { "kind": "reply_gap_high", "at": "2026-08-19T23:41:00+09:00", "session_id": 1187, "value_min": 184, "baseline_median_min": 5, "text": "화요일 밤에는 답장이 평소(5분)보다 긴 3시간 걸린 순간이 있었어요." }
  ],
  "safety": { "passed": true, "rewritten": [] }
}
```

**불변 규칙 (서버가 보장)**
- **상대 값은 응답 어느 곳에도 들어가지 않는다** — `summary`·`metrics` 는 `couple`/`mine` 만, `highlights[]`·`moments[]` 에는 발화자 필드가 없다 (ISSUE B3)
- `highlights`·`suggestions` 문장은 **`couple` 값만 근거로 삼는다**. `mine` 은 화면 표시용이며 LLM 입력에 들어가지 않는다 (P-1)
- `interpretations.length >= 2` — 각 항목은 **종결어미 없는 절**(`"바쁜 시기였을 수도"`). 프론트가 `", ".join(...) + " 있어요."` 로 한 문장을 만들어 카드가 **관찰·해석·제안 3문장**이 된다. 2개를 강제하는 건 원인을 단정하지 않기 위해서다 (P-1)
- `highlights`·`suggestions` 문장에 **숫자가 없다** — 에이전트 입력이 `{direction, magnitude}` 뿐이라 숫자가 나오면 지어낸 값이다 (ISSUE B3). 수치는 타임라인 그래프가 보여준다
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
  "sessions": [{ "session_id": 1187, "started_at": "...", "ended_at": "...", "initiator": "a", "initiated_by_me": true, "msg_count": 34 }],
  "metrics": {
    "range": {
      "question_rate": { "couple": 0.2, "mine": 0.1 },
      "reply_gap_median_min": { "couple": 12, "mine": 3 },
      "message_count": 145
    },
    "baseline": {
      "weeks": 8,
      "question_rate": { "couple": 0.23, "mine": 0.22 },
      "reply_gap_median_min": { "couple": 5, "mine": 4 },
      "message_count": 132.5
    },
    "comment": "평소보다 답장 간격이 뚜렷하게 길어졌어요."
  },
  "notes": [{ "note_id": 7, "author": "a", "body": "시험 끝나고 싸움", "created_at": "..." }]
}
```

**지표 규칙**
- `question_rate`는 API에서 `0.0~1.0` 비율을 유지하며, 퍼센트 변환은 프론트에서 한다.
- `reply_gap_median_min`은 기존 답장 간격 중앙값이며 단위는 분이다.
- `message_count`는 개인별로 나누지 않은 선택 구간의 커플 전체 메시지 수다.
- baseline은 선택 구간 직전 과거 데이터이며 최대 8주다. 비교에 필요한 과거 데이터가 부족한 값은 `null`로 유지한다.
- 날짜 범위 조회의 `baseline.message_count`는 baseline 실제 일평균에 선택 구간 길이를 곱해 환산한다. 기존 `start`/`end` 기간 길이에 임의로 하루를 더하지 않는다.
- `session_id` 조회의 `baseline.message_count`는 baseline에 포함된 과거 세션 `msg_count`의 평균이다.
- `comment`는 `couple` 값만 사용한 숫자 없는 방향성 한 문장이다. 기존 지표 band 규칙으로 코드가 결정론적으로 만들며 LLM을 호출하지 않는다. (윤석 구현, 2026-08-25)
- `message_length_median`·`session_length_median`은 이 화면에서 제외한다(타임라인·리포트에는 계속 있음).

### 5.2 GET /api/couples/{couple_id}/review/sessions/{session_id}/messages

세션 카드를 펼칠 때 원문 메시지를 페이지 단위로 조회한다. 로그인한 사용자가 해당 커플의 구성원이어야 하며, 다른 커플의 세션은 조회할 수 없다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| offset | int | X | 기본값 0 |
| limit | int | X | 기본값 30, 최대 100 |

**Response 200**
```json
{
  "session_id": 1187,
  "total": 34,
  "messages": [
    { "message_id": 81001, "at": "...", "mine": true, "text": "오늘 하루는 어땠어?" }
  ],
  "next_offset": 30
}
```

- `mine`은 저장 축(`a`/`b`)을 노출하지 않고 현재 요청자 기준으로 계산한다.
- 본문은 DB에서 암호화 상태로 보관하며, 권한 확인 후 응답 생성 시점에만 복호화한다.
- `next_offset`이 `null`이면 마지막 페이지다.
- 존재하지 않거나 다른 커플에 속한 세션은 **404**를 반환한다.

### 5.3 POST /api/couples/{couple_id}/notes

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| range_start | ISO 8601 | O | |
| range_end | ISO 8601 | O | >= range_start |
| body | string | O | 1~500자 |

**Response 201**: `{ "note_id", "author": "a", "body", "range_start", "range_end", "created_at" }`

### 5.4 DELETE /api/couples/{couple_id}/notes/{note_id}

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
1. Supervisor가 intent 분류: `fact_query` / `metric_query` / `report_query` / `term_count` / `top_term` / `advice_request` / `other`
2. `fact_query` → 컬렉션 A 검색(couple_id 필터 + focus_range 가중) → 인용 포함 답변
3. `metric_query` → `get_metrics` 툴 → 수치 답변
4. `report_query` → `get_report` 툴 → 과거 리포트 내용 답변
5. `term_count` → `count_term` 툴 → 템플릿 답변. **LLM 0회** — `몇 번`·`몇 회`·`얼마나 자주` 를 regex 로 먼저 잡아 대상 단어를 뽑고(따옴표 우선, 없으면 패턴 앞 어절), 실패할 때만 LLM 으로 단어만 추출한다. 숫자는 코드가 만든다 (P-2)
6. `top_term` (2026-08-27 추가) → `top_terms` 툴 → 템플릿 답변. **LLM 0회** — "가장/제일 많이 쓴 단어" 류를 regex 로 먼저 잡는다. `term_count`와 달리 특정 단어를 안 짚고 전체 순위를 묻는 질문이다
7. `advice_request` → 검색·툴 호출 없이 안내 문구로 리다이렉트, `answer: null`. **감지는 여전히
   LLM 0회**(regex `ADVICE_PATTERN` 또는 `chat_intent` 분류), 다만 안내 문구 자체는 **2026-08-27부터
   `chat_answer`가 LLM 1회로 생성**(이전엔 완전 고정 문구였음, 윤아 요청). `banned_patterns.txt`
   (safety_agent.py와 동일 목록)로 스캔해서 조언/판단 표현이 조금이라도 섞이면 무조건 기존 고정
   문구(`ADVICE_FALLBACK_TEXT`, `chat_answer_agent.py`)로 폴백한다 — "관계를 판단하지 않는다"는
   원칙을 LLM 혼자에게 맡기지 않는 이중 방어
8. `other` → "대화 기록·지표·리포트에 대해 물어봐 주세요"
9. 답변에 인용이 하나도 없으면 서버가 `answer`를 버리고 `"관련 기록을 찾지 못했어요"`로 대체 (근거 없는 말 금지)
10. (2026-08-27 추가) `focus_range`가 비어 있어도 메시지에 "이번주"/"저번주"/"오늘"/"어제"/"이번달"/"저번달" 표현이 있으면 그걸 실제 날짜 범위로 파싱해 `fact_query`/`metric_query`/`report_query`/`term_count`/`top_term` 검색·집계에 그대로 쓴다(`chat_supervisor._effective_range()`). `focus_range`가 이미 있으면 그게 항상 우선이고 파싱은 보충용이다

**`term_count` 세부 규칙**
- **커플 합산만 답한다.** "내가 몇 번", "쟤가 몇 번" 처럼 사람을 지목해 물어도 합산으로 답하고 `"누가 얼마나 썼는지는 알려드리지 않아요"` 를 덧붙인다. 발화자별 횟수는 숨기는 게 아니라 **계산·저장하지 않는다** (`term_count_cache` 에 `sender` 컬럼 없음) — P-3 예외("내 단어는 본인만")가 우회로 무너지는 것을 막는다
- **P-4 예외**: 이 답변에는 인용을 붙이지 않는다(`citations: []`). 인용 카드가 발화자를 드러내기 때문이며, 숫자와 주별 추이 자체가 근거다. 실제 대화를 보려면 `fact_query` 로 다시 물으면 된다
- 매칭은 완전일치 · 접두일치(`사랑` → `사랑해`) · 같은 canonical(`조아` → `좋아`). 합산된 변형은 답변에 함께 표기
- 0건이면 지어내지 말고 `"'{단어}'은 대화 기록에서 찾지 못했어요"`

```json
{ "intent": "term_count", "answer": "'사랑해'는 전체 대화에서 44번 나왔어요 (사랑해 41 · 사랑행 3).", "citations": [], "redirect": null, "trace_id": "uuid" }
```

**`top_term` 세부 규칙 (2026-08-27 추가)**
- **커플 합산 빈도 상위 5개 중 답변엔 최대 4개만 노출**("1위 + 그다음 최대 3개"). `count_term`과 마찬가지로 발화자별 순위는 계산하지 않는다 (P-3 예외 보호)
- `couple_lexicon`에서 `sentiment=exclude`로 분류된 표면형(PII·욕설·이름·호칭 등)은 순위에서 제외한다
- 이 답변에도 인용을 붙이지 않는다(`citations: []`) — `term_count`와 같은 이유
- 셀 만한 단어가 하나도 없으면 지어내지 말고 `"아직 단어를 셀 만한 대화 기록이 없어요."`

```json
{ "intent": "top_term", "answer": "가장 많이 쓴 단어는 '사랑해'이에요 (12번). 그다음은 치킨 5번 · 보고싶어 4번 순이에요.", "citations": [], "redirect": null, "trace_id": "uuid" }
```

**Response 200**
```json
{
  "intent": "fact_query",
  "answer": "2026년 3월 14일 저녁 대화에서 A가 처음 '자기야'라고 불렀어요.",
  "citations": [{ "session_id": 812, "at": "2026-03-14T19:22:00+09:00", "sender": "a", "snippet": "자기야 뭐해" }],
  "redirect": null,
  "trace_id": "uuid",
  "metrics": null
}
```

**`metric_query` 응답 예시 (2026-08-25 결정, ISSUE A7)** — 숫자는 `metrics` 카드로 항상 나가고, `answer`는 일반 질문이면 방향 문장 1줄뿐:
```json
{
  "intent": "metric_query",
  "answer": "지난 8주보다 답장이 많이 느려졌어요.",
  "citations": [],
  "redirect": null,
  "trace_id": "uuid",
  "metrics": {
    "range": { "question_rate": { "couple": 0.2, "mine": 0.1 }, "reply_gap_median_min": { "couple": 12, "mine": 3 }, "message_count": 187 },
    "baseline": { "weeks": 8, "question_rate": { "couple": 0.23, "mine": 0.22 }, "reply_gap_median_min": { "couple": 5, "mine": 4 }, "message_count": 210 },
    "comment": "지난 8주보다 답장이 많이 느려졌어요"
  }
}
```
**2026-08-25 수정**: 단, "정확히 몇 %야?"처럼 수치 자체를 콕 집어 물으면 `answer`도 실제 숫자를 그대로 답한다(카드로 미루지 않음) — 예: `"answer": "지금 질문 비율은 20%예요. 지난 8주 평균(23%)보다 조금 낮아졌어요."` (`range`/`baseline` 값을 그대로 옮기며, `question_rate`의 %표기(100배)만 예외적으로 허용, 그 외 계산 없음). 그 외 일반 질문은 위 예시처럼 숫자 없는 방향 문장만.

`metrics`는 metric_query 외에는 항상 `null`. 프론트는 이 카드를 돌아보기 화면과 동일한 컴포넌트로 그리면 됨(§5.1 `ReviewMetrics`와 타입 동일).

**advice_request** (2026-08-27부터 `redirect` 문구가 LLM 생성 — 매번 똑같은 문장이 아닐 수 있음.
아래는 mock/폴백 시 나오는 예시)
```json
{ "intent": "advice_request", "answer": null, "citations": [], "redirect": "요즘 연락이 뜸해서 신경 쓰이시는군요. 이 챗봇은 관계를 판단하지 않지만, 대신 요즘 대화가 어땠는지는 같이 볼 수 있어요.", "trace_id": "uuid" }
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
| `get_metrics` | `(couple_id, focus_range?) → {range: RangeMetrics, baseline: BaselineMetrics, comment: str}` — 돌아보기(§5.1) 화면과 동일한 range-vs-baseline 형태 (2026-08-25 결정, ISSUE A7). `comment`는 코드가 숫자 없이 방향만 생성(`services/projection.py`) | Postgres 조회, `build_review()` 로직 재사용 권장 |
| `get_report` | `(couple_id, week_start) → report` | Postgres 조회 |
| `search_knowledge` | `(metric, direction, k=5) → [{doc, section, text, source}]` | 지식 dict (`data/knowledge/interpretations`, 메모리) |
| `get_suggestion_templates` | `(metric, direction) → [{template_id, text}]` | 지식 dict (`data/knowledge/templates.json`, 메모리) |
| `count_term` | `(couple_id, term, start?, end?) → {term, total, matched_forms: [{form, count}], by_week: [{week_start, count}]}` | **커플 합산, 발화자별 미제공.** 감성 사전과 무관 — 임의 단어를 센다. 캐시(`term_count_cache`) 히트면 즉시, 미스면 본문을 메모리에서 복호화해 세고 캐시 후 폐기(~1-2s). LLM 미사용 |
| `top_terms` | `(couple_id, start?, end?, limit=5) → {terms: [{term, count}, ...]}` (2026-08-27 추가) | **커플 합산 빈도 상위 N개, 발화자별 미제공.** `count_term`과 같은 원문 소스를 쓰지만 대상 단어를 안 받고 전체 순위를 낸다. `couple_lexicon`의 `sentiment=exclude` 표면형은 뺀다. 캐시 없음(요청 자체가 드묾). LLM 미사용 |

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
