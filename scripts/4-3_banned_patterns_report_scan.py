# 역할: Phase 4 — 4-3 "금지 표현 regex 전 리포트 스캔" (담당 윤아, TC-API-005-9).
#       개별 리포트 생성 시점 검증(interpret_agent의 생성 시 재요청, safety_agent의 재작성)은
#       이미 코드로 되어 있지만, 이건 유닛테스트 수준(고정 fixture)이라 "실제로 만들어진 리포트
#       전체"를 훑어본 적은 없음. 이 스크립트는 실제 Postgres에 저장된 모든 리포트(status='generated')
#       를 꺼내서, banned_patterns.txt(FR-004) 규칙 8종을 LLM 생성 문장(highlights[].observation /
#       highlights[].interpretations[] / suggestions[].text)에 전부 다시 통과시켜 0건인지 최종 확인한다.
#       (moments[].text는 코드가 만들고 수치가 근거라 대상 아님 — safety_agent.py의 _targets()와 동일 기준)
#
#       즉 "생성 시 걸렀다"가 아니라 "실제로 DB에 들어간 최종 결과물이 진짜로 깨끗한가"를 배포 직전에
#       한 번 더 확인하는 감사(audit) 스크립트. Day3 오전(Phase 4) 통합 단계에서, report_backfill이
#       실제(또는 데모) 데이터로 실 watsonx를 돌려 리포트를 만든 뒤에 실행하는 게 의미 있다 — 리포트가
#       하나도 없으면(아직 실행 전이면) 그 사실을 그대로 알려준다.
#
# 사용법 (레포 루트에서, 본인 PC 터미널 — venv 활성화 후):
#   python scripts/4-3_banned_patterns_report_scan.py
#   (.env 의 POSTGRES_DSN 사용. docker compose로 띄운 채 호스트에서 실행하면 postgres 호스트명이
#    안 풀리므로 자동으로 localhost로 바꿔서 접속한다 — SCAN_POSTGRES_DSN 환경변수로 강제 지정 가능)
#   특정 커플만 보려면: python scripts/4-3_banned_patterns_report_scan.py <couple_id>
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
RESULT_PATH = Path(__file__).resolve().parent / "4-3_banned_scan_raw.json"

sys.path.insert(0, str(REPO_ROOT / "api"))  # app.* 를 import 하기 위함


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


def resolve_dsn(env: dict[str, str]) -> str:
    override = os.environ.get("SCAN_POSTGRES_DSN")
    if override:
        return override
    dsn = env.get("POSTGRES_DSN", "postgresql://couple:couple@postgres:5432/couple_report")
    # docker-compose 네트워크 안의 호스트명(postgres)은 호스트 PC 터미널에서 안 풀리므로
    # docker-compose.yml의 ports: ["5432:5432"] 매핑을 이용해 localhost로 바꿔서 접속한다.
    return dsn.replace("@postgres:", "@localhost:")


def extract_targets(report_json: dict[str, Any]) -> list[tuple[str, str]]:
    """(필드 경로, 텍스트) 목록. safety_agent.py의 _targets()와 동일한 대상 기준
    (moments 제외)을 report_json 저장 형태에 맞춰 재구성한다."""
    targets: list[tuple[str, str]] = []
    for i, highlight in enumerate(report_json.get("highlights") or []):
        observation = highlight.get("observation")
        if observation:
            targets.append((f"highlights[{i}].observation", observation))
        for j, interp in enumerate(highlight.get("interpretations") or []):
            targets.append((f"highlights[{i}].interpretations[{j}]", interp))
    for i, suggestion in enumerate(report_json.get("suggestions") or []):
        text = suggestion.get("text")
        if text:
            targets.append((f"suggestions[{i}].text", text))
    return targets


async def main() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.agents.safety_agent import load_banned_patterns

    env = load_env(ENV_PATH)
    dsn = resolve_dsn(env)
    patterns = load_banned_patterns()

    couple_filter = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"DB 접속: {dsn.split('@')[-1] if '@' in dsn else dsn}")
    print(f"규칙 {len(patterns)}개 (banned_patterns.txt) 로드 완료")
    print("=" * 70)

    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            if couple_filter:
                await cur.execute(
                    """
                    SELECT couple_id, week_start, report_json FROM reports
                     WHERE status = 'generated' AND report_json IS NOT NULL
                       AND couple_id = %s
                     ORDER BY couple_id, week_start
                    """,
                    (couple_filter,),
                )
            else:
                await cur.execute(
                    """
                    SELECT couple_id, week_start, report_json FROM reports
                     WHERE status = 'generated' AND report_json IS NOT NULL
                     ORDER BY couple_id, week_start
                    """
                )
            rows = await cur.fetchall()

    if not rows:
        print("[알림] status='generated' 인 리포트가 DB에 하나도 없습니다.")
        print("       report_backfill이 아직 실 데이터로 실행되기 전이거나(Phase 4 통합 전),")
        print("       모두 insufficient_baseline/pending/failed 상태라는 뜻입니다.")
        print("       실제(또는 데모) 데이터로 리포트가 생성된 뒤 다시 실행해주세요.")
        return

    print(f"리포트 {len(rows)}건 스캔 시작 (couple_id×week_start 기준)\n")

    hits: list[dict[str, Any]] = []
    total_sentences = 0
    per_report: list[dict[str, Any]] = []

    for row in rows:
        targets = extract_targets(row["report_json"] or {})
        total_sentences += len(targets)
        report_hits = []
        for field, text in targets:
            for pattern in patterns:
                if pattern.search(text):
                    report_hits.append(
                        {"field": field, "text": text, "pattern": pattern.pattern}
                    )
        entry = {
            "couple_id": str(row["couple_id"]),
            "week_start": str(row["week_start"]),
            "sentence_count": len(targets),
            "hits": report_hits,
        }
        per_report.append(entry)
        if report_hits:
            hits.extend({**h, "couple_id": entry["couple_id"], "week_start": entry["week_start"]} for h in report_hits)
            print(f"  [✗] {row['couple_id']} / {row['week_start']} — {len(report_hits)}건 발견")
            for h in report_hits:
                print(f"        - {h['field']}: {h['text']!r}  (규칙: {h['pattern']})")
        else:
            print(f"  [✓] {row['couple_id']} / {row['week_start']} — {len(targets)}문장 전부 통과")

    print("=" * 70)
    print(f"전체: 리포트 {len(rows)}건, 문장 {total_sentences}개 검사, 금지 표현 {len(hits)}건 발견")
    if hits:
        print("\n⚠️ 금지 표현이 실제 저장된 리포트에서 발견됨 — safety_agent 재작성을 통과하고도")
        print("   남아있었다는 뜻이라 원인 파악 필요(TC-API-005-9 실패). 위 목록을 윤석/해찬과 공유하세요.")
    else:
        print("\n✓ TC-API-005-9 통과 — 실제 저장된 모든 리포트에서 금지 표현 0건.")

    RESULT_PATH.write_text(
        json.dumps({"reports": per_report, "hit_count": len(hits)}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
