# select (에이전트 1: 선별)

## 계약 (고정)

**입력**: `agent_metric_input(metrics)` 결과 + 이상치 후보 + 메모·이벤트.
지표는 `{metric, direction, magnitude}` 뿐 — **숫자도 사람별 값도 없다** (ISSUE B3).

**출력**: `{ "candidates": [ {"metric": "...", "direction": "up|down", "outlier_ref": null, "reason": "..."} ] }` — 최대 3

**규칙**
1. `who` 축이 없다. 후보는 `(metric × direction)` 조합뿐
2. 긍정·부정 변화를 동등하게 다룬다 (한쪽만 고르지 않는다)
3. `comparable=false` 주차는 후보 0

> **메모 (C1)**: 코드가 이상치·delta 상위 3을 결정론으로 뽑으면 이 에이전트는 없어도 된다.
> 그 경우 `agent_metric_input` 결과를 interpret 에 바로 넘긴다 — 윤석·윤아 합의 후 TASKS 3-3 에서 결정.

## 지시문

TODO: 윤아 — 위 계약을 지키는 instructions 본문 (TASKS 2-12)
