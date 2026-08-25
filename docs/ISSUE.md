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

### A4. [x] 담당 재배분
- **문제**: 윤석 17.5건(34%), Phase 2 `2-1→2-2`, `2-3→2-4` 직렬 + Phase 3 Supervisor 2개·큐까지 크리티컬 패스 전부 집중.
- **제안**: 2-1 auth → 시여 / 3-12 Qdrant 삭제 → 윤아 / 4-2 OpenShift 통합 테스트 → 해찬 / 4-5 Mock 백업 점검 → 형준. 결과: 윤석 14(27%), 시여 10, 윤아 11, 해찬 11, 형준 5.5
- **영향**: `TASKS.md` §5~7, §10
- **결정**:

### A5. [x] canonical 묶기 범위 (A1이 (b)/(c)일 때)
- **문제**: LLM 정규화가 철자 변형(`조아`→`좋아`)만 묶을지, 동의어(`고마워`/`감사`/`땡큐`)까지 묶을지.
- **선택지**: 변형만 / 동의어까지
- **영향**: `prompts/lexicon.md`, TC-METRIC-007 고정 케이스
- **결정**: **철자 변형만 묶음**(`조아`·`좋앙`→`좋아`). 동의어(`고마워`/`감사`/`땡큐`)는 분리 — 커플 고유 표현이 보이는 게 가치 있고, 동의어 묶기는 LLM 판단이 흔들려 재현성을 해침.

### A6. [x] 이미지에 `data/` 가 없다 — 배포 시 지식·템플릿·시드 사전 0개
- **문제**: `api/Dockerfile` 은 `app` 과 `mock` 만 COPY 한다. `KNOWLEDGE_DIR=data/knowledge` 는 repo 루트라 이미지에 안 들어간다. docker compose 는 `./data:/app/data:ro` 볼륨으로 가려주지만 **OpenShift 에는 그 볼륨이 없다.**
  - **무증상이라 더 나쁘다**: `load_knowledge` 는 디렉터리가 없어도 예외를 안 내고 빈 값을 돌려준다 → 지식 문서·제안 템플릿·시드 사전이 전부 0개인 채로 앱이 정상 기동하고, 리포트의 `suggestions`·`sources` 가 조용히 빈다. 감성 단어 카드도 시드가 없어 빈다
- **선택지**
  - (가) 빌드 컨텍스트를 repo 루트로 (`build: {context: ., dockerfile: api/Dockerfile}`) + `COPY data ./data`. 컨텍스트가 커지지만 경로 문서를 안 건드림
  - (나) `data/knowledge` 를 `api/data/knowledge` 로 이동. 컨텍스트 그대로, `.env.example`·SCAFFOLD·TRD·knowledge.py 주석의 경로 수정. 윤아 편집 범위 문서도 같이
  - (다) OpenShift 에서 ConfigMap 으로 주입. 파일이 늘면 관리 부담
- **영향**: `api/Dockerfile`, `docker-compose.yml`, `openshift/20-api-deployment.yaml`, `.env.example`, `SCAFFOLD` 트리, TASKS 2-10
- **결정**: **(가) 빌드 컨텍스트를 repo 루트로.** `docker-compose` 의 `build: {context: ., dockerfile: api/Dockerfile}`, Dockerfile 이 `COPY data ./data` 추가. 경로 문서(`KNOWLEDGE_DIR=data/knowledge`)를 안 건드리고 윤아 편집 범위도 그대로라 (나) 보다 파급이 작다. 컨텍스트가 커지는 건 `.dockerignore` 로 처리(`.git`, `node_modules`, `docs`, `openshift`, `web/dist` 등 제외).
  - compose 의 `./data:/app/data:ro` 볼륨은 **유지** — 개발 중에는 볼륨이 이미지 것을 덮어써 재빌드 없이 지식 문서를 고칠 수 있고, OpenShift 에는 볼륨이 없으니 이미지 안의 것을 쓴다
  - **검증**: 이미지 빌드 후 컨테이너 안에서 `load_knowledge` 실행 → `seed_lexicon: 61` (수정 전이면 0). `docs`·`templates` 가 0 인 건 파일이 아직 비어서고(TASKS 1-7·2-11), A6 와 무관

### A7. [ ] 챗봇 `metric_query` 의 수치·노출 정책
- **문제**: B3(지표는 `couple`+`mine` 만)·B4(LLM 문장에 숫자 금지)를 리포트 경로에만 적용했다. 챗봇 `metric_query` 는 공백이다.
  - `tools.get_metrics` 가 저장형(`a`/`b`)을 주면 B3 가 이 경로로 무너진다
  - LLM 에 숫자를 그대로 주면 B4 와 어긋난다. 반대로 밴딩만 주면 "얼마나 빨라?" 에 답을 못 한다
  - `term_count` 는 A3 에서 "커플 합산만, 사람 지목해도 합산 + 안내 문구"까지 정했는데 `metric_query` 만 빠져 있다
- **선택지**: (가) `term_count` 와 같은 규칙 — 커플 값만, 숫자 허용 / (나) 커플 값 + `mine` 까지 (본인이 물었으니), 숫자 허용 / (다) 리포트와 동일하게 밴딩만
- **영향**: `tools/get_metrics.py`, `prompts/chat_answer.md`, `agents/chat_supervisor.py`, API_SPEC §6.1·§8, TC-API-008-2
- **결정**:

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

### B3. [x] 지표의 사람별 나란히 노출

- **문제**: B1에서 "사실의 사람별 표시는 허용"으로 P-1을 넓히는 안을 **기각**하고 "내 단어"를 본인에게만 보이는 쪽을 택했고(`P-1 수정 불필요 (비교 프레임 없음)`), A2에서 `initiation_ratio`를 뺀 이유 중 하나도 `a/b 비교 프레임`이었다. 그런데 추이 지표는 여전히 `{a: 0.18, b: 0.22}`로 나란히 나간다 — **단어는 본인 것만, 지표는 둘 다**라는 불일치. 문장에서 비교를 지워도 그래프에 두 선이 나란히 있으면 사용자가 스스로 비교한다.
  - 기획서 원안이라 아무도 건드리지 않았을 뿐. 리포트 톤 의견(문장에서 개인 지목 금지)을 검토하다 드러났지만, 그 의견 없이도 정리되어야 할 항목
- **선택지**: (가) 커플 합산만 / (나) 커플 합산 + 내 것(`mine`) / (다) 리포트·타임라인만 합산하고 돌아보기는 a/b 유지
- **결정**: **(나) `{couple, mine}`.** "내 단어"와 같은 패턴 — 상대 값은 표시를 안 하는 수준이 아니라 **응답에 담지 않는다**. 자기 성찰 가치는 살리고 상대와의 직접 비교는 막는다.
  1. **저장형 ≠ 응답형.** `weekly_metrics.summary`·`reports.report`는 커플당 한 행이므로 사람별(a/b)로 저장하고, 응답 조립 시점에 `services/projection.py`가 `{couple, mine}`으로 투영. `weekly_terms`(양쪽 저장 → 응답만 필터)와 같은 구조. `summary_hash`는 저장형 기준이라 요청자와 무관 — 규칙 변경 없음. **DB 스키마 변경 없음**(둘 다 JSONB)
  2. **`couple` 정의**: 사람별 값의 평균이 아니라 **합친 뒤** 계산. `question_rate` = 풀링 비율, `message_length_median` = 합친 분포의 중앙값, `reply_gap`·`resume_delay` = 양방향 전체의 중앙값
  3. **`comparable`은 couple 기준** 하나. baseline·delta는 `couple`·`a`·`b` 세 축 모두 계산(저장형)
  4. **이상치 판정 분포는 사람별 유지.** 평소 속도가 다른 두 사람을 합치면 한쪽의 평범한 지연이 안 잡히고 다른 쪽의 평범한 답이 low outlier로 잡힌다. 응답에서 `who`만 제거(`weekly_metrics.outliers`엔 유지)
  5. **`Highlight.who`·`Moment.who` 응답에서 제거.** 계약을 두 번 깨지 않기 위해 함께 처리
  6. **LLM 입력 경계**: 에이전트에는 `couple` 값만. `mine`은 코드가 응답에 붙이는 표시용이며 프롬프트에 들어가지 않는다 → LLM이 비교 문장을 만들 재료 자체가 없음. `SelectOut.candidates[].who` 제거 → 후보 축이 (metric × direction)만 남아 C1의 select+interpret 통합과 맞물림
  7. **역산 불가**: 노출값이 전부 중앙값·풀링 비율이고 응답에 사람별 메시지 수가 없어 `couple`+`mine`으로 상대 값을 되돌릴 수 없다. 근거를 P-3에 명시
  8. **라우터는 응답 모델을 직접 만들지 않는다.** `projection.build_timeline`·`build_report`·`build_review` 만 호출한다. 투영이 조립 함수 안쪽에 있어야 읽기 경로(타임라인·리포트·돌아보기) 세 곳에서 빠뜨리는 일이 없다. grep 한 번으로 검사 가능: 라우터에 `WeekSummary(`·`TimelineResponse(`·`model_validate` 가 없어야 한다
  9. **`CoupleMine.mine`·`MetricComparison.mine` 은 필수**(널은 허용, 키는 필수). 8을 우회해 직접 모델을 만들면 `ValidationError: weeks.0.summary.question_rate.mine Field required` 로 즉시 터진다. `extra="forbid"` 는 기각 — `_pick` 이 입력에 따라 키 개수를 달리 내놓아(summary 2개 / metrics 6~7개) 정상 데이터에서 오작동한다
  - `me`는 `app/deps.py current_member` 의존성에서 온다. auth 미구현(TASKS 2-1) 구간엔 `"a"` 고정이고, 붙일 때 이 파일만 고치면 라우터는 그대로. 테스트는 `dependency_overrides` 로 A/B 교체 — B1의 `sentiment.mine`도 같은 조건이라 새 블로커 아님
  - **범위 밖(다음 작업)**: `interpretations >= 2` → 1개(2~3문장 구조), "우리" 주어 문장 재작성, 프롬프트·`banned_patterns.txt`·`templates.json` (윤아, TASKS 2-12)
  - 반영: `metrics.py`(couple 축), `services/projection.py`(신규), `models/api.py`(`ABFloat`→`CoupleMine`, `MetricComparison`, `Highlight.who`·`Moment.who` 삭제), `types.ts`, 라우터 3·목 JSON 3, `API_SPEC` §4.1·4.2·5.1, `REQUIREMENTS` P-3·FR-002·FR-004, `TRD` §5.2, `TEST_CASES` TC-METRIC-002·008·TC-API-005, `tests/test_metrics.py`·`tests/test_projection.py`

---

### B4. [x] 리포트 문장 톤 — "우리는 ~한 편이에요"

- **문제**: 외부 의견 — `"oo님이 더 ~했어요"`(X) → `"우리는 ~한 편이에요"`(O). 누가 잘했다/못했다가 아니라 이 커플 고유의 패턴을 관찰하는 톤. 구조는 관찰 → 해석 → 제안, **2~3문장**. 정량 수치는 백엔드 계산까지만 두고 프롬프트에는 경향만 넘겨 LLM 이 비교 문장을 만들 길을 원천 차단.
- **B3 이 이미 처리한 것**: 개인 지목(`Highlight.who`·`Moment.who` 삭제), 개인 수치 노출(`mine` 만 전송), "프롬프트에 누가 몇 %를 안 넘긴다"의 절반(`couple` 값으로 제한). 남은 건 문장 쪽.
- **결정**
  1. **"2~3문장" vs `interpretations >= 2`** — 계약 유지 + **렌더 병합**. `interpretations[]` 각 항목을 **종결어미 없는 절**로 규정하고(`"바쁜 시기였을 수도"`), `HighlightCard.joinInterpretations` 가 `", ".join + " 있어요."` 로 한 문장을 만든다. 사용자는 관찰·해석·제안 **3문장**을 보고, 코드는 "가능성을 둘 이상 제시했는가"를 계속 검증한다.
     - `≥2` 는 장식이 아니라 **P-1(단정 금지)의 구현 장치**다. 1개로 줄이면 그 한 문장이 *그* 설명으로 읽히고, 단정 방지가 프롬프트 지시에만 의존하게 된다
  2. **LLM 에 숫자를 넘기지 않는다.** 코드가 `metrics.band(couple, baseline_couple)` 로 `{direction: up|down|steady, magnitude: slight|clear}` 를 만들어 넘긴다 (결정론, P-2). 임계값 `BAND_STEADY=0.15` · `BAND_SLIGHT=0.35`. `agent_metric_input()` 이 `steady`·비교 불가 지표를 걸러 후보만 넘긴다.
     - 따라서 **문장에 숫자가 나오면 지어낸 값**이다 → `banned_patterns` 가 `\d+\s*(%|퍼센트|배|점|등급)` 를 잡는다. TC-AGENT-004-4 `"질문이 30% 줄었어요"` 를 `passed` → **`rewritten`** 으로 수정
     - 수치는 이미 타임라인 그래프가 `couple`/`mine` 추이로 보여준다 — **문장은 정성, 숫자는 그래프**
  3. **`banned_patterns.txt` 초안 작성** (regex 는 결정론이라 코드·테스트 영역). 인물 지목 / 두 사람 비교 / 수치 / 점수·등급 / 가치 판단 / 원인 단정 / 명령·당위 / 관계 판정 8군.
     - **기준선 비교는 막지 않는다**: `"지난 4주에 비해"` 는 사람 비교가 아니다. `에 비해`·`보다` 를 통째로 막으면 정상 문장이 걸린다 — 인물 토큰이 앞에 올 때만 잡는다
     - 검사 시점은 `names.ts` 의 A/B→실명 치환 **전**, 서버. 그래서 인물 규칙은 A/B 토큰 기준
     - `tests/test_banned_patterns.py` 가 잡아야 할 11문장 / 통과해야 할 8문장(의견이 제시한 톤 예시 그대로)으로 검증
  4. **프롬프트는 계약만 고정**하고 지시문·톤 예시는 윤아 (TASKS 2-11·2-12). `select.md`·`interpret.md`·`suggest.md`·`safety.md` 에 입출력 스키마와 규칙을 적고 `## 지시문` 은 TODO 로 남김
  - **검수 대상 경계**: LLM 문장(`observation`·`interpretations`·`suggestions[].text`)만. `moments[].text` 는 코드 생성이고 수치가 근거라 대상 아님
  - 반영: `metrics.band`·`agent_metric_input`, `prompts/*.md` 4개, `banned_patterns.txt`, `HighlightCard.tsx`·`Report.tsx`, `report_stored.json`, API_SPEC §4.2 불변 규칙, REQUIREMENTS FR-004, TRD §5.2, TC-AGENT-001·002·003·004, `tests/test_banned_patterns.py`

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

### C7. [x] `messages` 세션 FK 가 세션 삭제 시 터진다 (윤석)
- `init.sql`: `FOREIGN KEY (couple_id, session_id) REFERENCES sessions(...) ON DELETE SET NULL`. 다중 컬럼 FK 의 `SET NULL` 은 참조 컬럼을 **전부** NULL 로 만드는데 `couple_id` 는 `NOT NULL` → 재업로드로 세션을 재분할하며 기존 행을 지우면 not-null 위반.
- 할 것: PG15+ 문법 `ON DELETE SET NULL (session_id)` 로 (compose 는 `postgres:16-alpine`). 또는 FK 를 빼고 앱이 정합성 책임.
- **검증 완료 (2026-08-24)**: `postgres:16-alpine` 에 스키마를 올리고 재현. Postgres 가 만드는 문장이
  `UPDATE ONLY messages SET couple_id = NULL, session_id = NULL ...` → `null value in column "couple_id" ... violates not-null constraint`.
- **반영**: `ON DELETE SET NULL (session_id)` 로 수정. 재검증에서 세션 삭제 시 `couple_id` 보존 + `session_id` 만 NULL 확인.
  같은 DB 에서 B2(커플 해제·사용자 탈퇴 CASCADE)도 함께 확인 — messages·notes·weekly_terms 전부 0.
- **주의**: `init.sql` 은 `/docker-entrypoint-initdb.d/` 라 **DB 데이터 디렉터리가 비어 있을 때만** 실행된다. 이미 띄워본 사람은 `docker compose down -v` 필요.
- 파일: `postgres/init.sql`, TC-API-003

### C8. [ ] `messages.session_id` 를 채우는 단계가 흐름에 없다 (윤석)
- FR-002 는 `5. 메시지 저장 → 6. 세션 분할` 순서인데 `messages.session_id` 에 세션 FK 가 걸려 있다. NULL 로 INSERT 한 뒤 세션 생성 후 UPDATE 하는 단계가 필요한데 문서에도 코드에도 없다.
- 안 채우면 조용히 NULL 로 남아 `idx_messages_session` 을 쓰는 인용·evidence·돌아보기 조회가 빈 결과를 준다.
- **문서 반영됨 (2026-08-24)**: FR-002 처리 규칙 6 에 `sessions` upsert → `messages.session_id` UPDATE 단계 명시, TC-API-003-12 추가.
- **남은 것(윤석)**: 실제 구현. 2-3 에서 `routers/upload.py` 에 UPDATE 단계를 넣는다.
- 파일: `routers/upload.py`(구현), `REQUIREMENTS` FR-002 ✓, `TEST_CASES` TC-API-003-12 ✓

### C9. [ ] `interpretations` 절 형식에 방어가 없다 (윤석 + 윤아)
- B4 는 각 항목을 **종결어미 없는 절**로 규정하고 프론트가 `", ".join + " 있어요."` 로 합친다. 프롬프트(윤아)와 렌더(시여)가 두 파일에 걸쳐 맞물려 있는데 **코드가 강제하지 않는다.**
  - LLM 이 완결 문장을 내면 화면에 `"바빴어요. 있어요."` — 경보 없이 사용자에게 나간다
  - 현재 테스트는 목 데이터의 마침표만 본다 (`test_banned_patterns.test_interpretations_are_clauses_not_sentences`). 실 LLM 출력은 검증 안 됨
- 할 것: `Highlight` 에 Pydantic validator — 각 항목이 `.`/`요`/`다` 로 끝나지 않고 길이 상한(40자). 위반 시 리포트 생성 단계에서 터져 화면까지 안 샌다 (LLM 출력 Pydantic 검증 실패 → 1회 재요청, TRD §1)
- 파일: `models/api.py`, `prompts/interpret.md`, TC-AGENT-002

### C11. [x] Qdrant payload 에 시각이 없어 챗봇 기간 검색이 불가능했다 (해찬, 3-1)
- 2-6 의 point payload 는 `{couple_id, session_id, chunk_idx, point_key}` 뿐이라 **시각 정보가 없었다.** 그런데 API_SPEC §8 의 `search_conversation` 은 `(couple_id, query, start?, end?, k=8)` — "지난달에 제주도 얘기" 같은 기간 한정 질문이 계약에 들어 있다.
- 검색 후 Postgres 에서 거르는 방법도 있지만, 그러면 **전체 기간에서 top-k 를 뽑고 나중에 버리는** 꼴이라 범위 안에 좋은 결과가 있어도 0건이 나올 수 있다.
- **결정**: payload 에 청크 자신의 `started_at`·`ended_at`(epoch 초)을 넣고 Qdrant 필터로 거른 뒤 top-k 를 뽑는다. 세션 단위가 아니라 **청크 단위** 범위라 긴 세션에서도 범위 밖 구간이 딸려오지 않는다. 본문·발화자는 여전히 payload 에 넣지 않는다(프라이버시 — 인용 카드는 Postgres 복호화로 조립).
- 기존 데이터 영향 없음: point id 가 결정론이라 `embed_sessions` 잡을 다시 돌리면 같은 id 로 덮어써진다. 실데이터 임베딩 전이라 재적재도 불필요.
- 파일: `services/embed_sessions.py`(build_points), `services/qdrant_service.py`(search_conversation), `tools/search_conversation.py`

### C10. [ ] 교육용 클러스터 수명 · 발표 후 데이터 정리 (해찬)
- OpenShift 클러스터(`c100-e.us-south.containers.cloud.ibm.com`)는 교육 기간에 발급받은 IBM Cloud ROKS 샌드박스. 발표(해커톤 마감)까지는 유지될 것으로 추정하지만, 강사·운영 쪽의 확정 공지는 아직 없음.
- `postgres-data`·`qdrant-storage` PVC(각 2Gi, [10-postgres-statefulset.yaml](../openshift/10-postgres-statefulset.yaml)·[11-qdrant-statefulset.yaml](../openshift/11-qdrant-statefulset.yaml))는 실제 카톡 대화(암호화 저장)를 담게 되므로, 클러스터가 예고 없이 회수되면 발표 직전 서비스 중단 리스크가 있고 동적 StorageClass 스토리지라 소액과금도 발생한다.
- 할 것: 클러스터 만료 시점을 강사·운영 쪽에 확인. **발표 종료 후에는 두 PVC를 정리**(`oc delete pvc postgres-data-postgres-0 qdrant-storage-qdrant-0` 형태) — 개인정보 보관 최소화 + 불필요한 과금 방지.
- 파일: `openshift/10-postgres-statefulset.yaml`, `openshift/11-qdrant-statefulset.yaml`

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

### D3. [x] Instana/OTel (해찬)
- 클러스터에 agent DaemonSet 없으면 전부 헛일. 1-V5 결과 후 결정. 없으면 `execution_trace` JSONB만 남김.
- **검증 (2026-08-24)**: 1-V5 완료 후 클러스터 전체를 직접 확인.
  1. `oc get daemonsets --all-namespaces` — 17개 전부 표준 OpenShift/IBM Cloud 인프라(calico-node, konnectivity-agent, dns-default 등). Instana 관련 0건
  2. `oc get pods --all-namespaces | grep instana` — 0건
  3. Instana 표준 에이전트 포트(42699)로 노드 hostIP 직접 연결 시도 → `Connection refused` (방화벽 차단이면 timeout이 났을 것 — refused는 그 포트에 듣는 프로세스 자체가 없다는 뜻이라 결정적 증거)
  4. 로그인 가능한 Instana 계정(`obs-bigdatalearning.instana.io`)이 있었으나, 팀 인프라용이 아니라 교육 과정 실습(개인 초대) 계정으로 확인됨 — 해커톤 클러스터 자체와는 별개
- **결정**: **없음. `execution_trace`만 사용.** NFR-005는 이미 `reports.execution_trace` JSONB + `trace_id`만 요구해서 코드 변경 없음.
  - 정리: `TRD` §9.1 계측 계획(자동 계측·에이전트/LLM/툴 스팬·EUM)은 **보류 표시**로 남김(에이전트가 생기면 재사용, 삭제하지 않음). `api/requirements.txt` 의 `instana==3.2.0` 제거(`AUTOWRAPT_BOOTSTRAP` 빈 값이라 원래도 비활성 — 죽은 의존성). `opentelemetry-api` 는 유지(에이전트 없이도 no-op으로 동작, 가벼움). `config.py` 의 `instana_agent_host`·`instana_service_name` 필드 제거. `.env.example` 주석 정정. `openshift/00-namespace-secret.yaml` ConfigMap 의 `INSTANA_SERVICE_NAME` 제거(보낼 곳이 없는 값)
  - TASKS 2-13은 이 검증으로 완료 처리. 4-6("Instana에서 트레이스 확인")은 전제가 없어져 스킵 — 리뷰 시 `execution_trace` 조회로 대체
  - 영향: `docs/TRD.md` §9.1, `api/requirements.txt`, `api/app/config.py`, `.env.example`, `openshift/00-namespace-secret.yaml`, `docs/TASKS.md` 2-13·4-6

### D4. [x] `ReviewMetrics` range/baseline 타입 확정 (윤석+시여)
- **결정**: `RangeMetrics`와 `BaselineMetrics`를 별도 타입으로 고정했다. 지표는 질문 비율·답장 시간·메시지 수 세 개이며, `question_rate`·`reply_gap_median_min`은 B3의 `{couple, mine}`, `message_count`는 개인별 분리 없는 커플 합산이다.
- baseline은 최대 8주다. 날짜 범위의 `baseline.message_count`는 baseline 일평균을 선택 구간 길이에 맞춰 환산하고, `session_id` 조회는 과거 baseline 세션 `msg_count` 평균을 사용한다.
- `metrics.comment`는 couple 값과 기존 band 규칙만으로 만드는 숫자 없는 방향성 한 문장이다. LLM은 호출하지 않는다.
- **반영·검증**: `models/api.py`, `services/review_metrics.py`, `services/projection.py`, `types.ts`, `Review.tsx`, API_SPEC §5.1, TC-API-006·005-13 및 관련 pytest/TypeScript build.

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
| 14 | 지표 노출 `{a,b}` → `{couple, mine}` (B3) | `metrics.py` couple 축, `services/projection.py`(신규), `CoupleMine`·`MetricComparison`, `Highlight.who`·`Moment.who` 삭제, 라우터·목·API_SPEC·REQUIREMENTS·TRD §5.2, TC-METRIC-008·`test_projection.py` |
| 15 | `reply_gap` 추이형 승격 (A2 후속) | `_trend_metrics` 에 `reply_gap_median_min`, `_gap_medians` 분리, 기준선 대상 3개. FR-002 지표 표·FR-004·API_SPEC §4.2·TC-METRIC-002-8 |
| 16 | 목 저장형/응답형 분리 (B3) | `api/mock/report_stored.json`(저장형) → `routers/reports.build_report` 가 projection 으로 투영. `api/mock/report_generated.json` 삭제, 프론트 목이 투영 결과와 같은지 `test_api_report.py` 가 검사 |
| 17 | 조립 지점 단일화 (B3) | `projection.build_timeline`·`build_report`·`build_review`, `app/deps.py current_member`(auth 스텁), 라우터 3개가 조립 함수만 호출. `mine` 필수로 우회 차단. `tests/test_api_read_paths.py` 3경로 검사 |
| 18 | 리포트 문장 톤 (B4) | `metrics.band`·`agent_metric_input`(숫자 대신 방향·정도), `banned_patterns.txt` 초안 + `test_banned_patterns.py`, `interpretations` 절 형식 + `HighlightCard.joinInterpretations` 3문장 병합, 프롬프트 4개 계약부, TC-AGENT-001~004 |

## 남은 것
- **A4** 담당 재배분 — 팀 회의 후 TASKS §5~7·§10 수정
- **A7** 챗봇 `metric_query` 수치 정책 — 챗봇 구현(3-6) 전까지
- **D3** Instana — 1-V5 후
- **C1~C10, D4** — TASKS 비고로 이관됨. 담당자가 구현 시 적용. 이 파일에선 추적 안 함
  (C7~C9 는 2026-08-24 스캐폴딩 점검에서 나온 것. **C7 은 수정·검증 완료**, C8 은 문서만 반영·구현은 2-3, C9 만 미착수)
  (C10 은 2026-08-24 oc 접속 확인 중 나온 것. 강사·운영 쪽 확인 전까지 미착수)
