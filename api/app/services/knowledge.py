# 역할: 지식 문서·제안 템플릿·감성 시드 사전 로더 — data/knowledge → 메모리 (참조: TRD §4.2, ISSUE D2·A1)
# 컬렉션 B 를 Qdrant 에 두지 않는다: (metric, direction) 조합이 ~10개라 dict 조회로 충분.
# 윤아 편집 범위: data/knowledge/interpretations/*.md, templates.json, sentiment_seed.json
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# interpretations/*.md 머리 메타: 첫 줄들에 `metric: question_rate` / `direction: down` / `source: ...`
_META_RE = re.compile(r"^(metric|direction|source|doc_type):\s*(.+)$", re.M)


@dataclass
class Knowledge:
    # (metric, direction) → [{"doc", "section", "text", "source"}]
    docs: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    # (metric, direction) → [{"template_id", "text"}]
    templates: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    # 공용 시드 사전: term → (canonical, polarity)  — couple_lexicon 초기값 (source='seed')
    seed_lexicon: dict[str, tuple[str, str]] = field(default_factory=dict)

    def search(self, metric: str, direction: str, k: int = 5) -> list[dict]:
        return self.docs.get((metric, direction), [])[:k]

    def suggestion_templates(self, metric: str, direction: str) -> list[dict]:
        return self.templates.get((metric, direction), [])


def load_knowledge(root: Path) -> Knowledge:
    k = Knowledge()

    for md in sorted((root / "interpretations").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        meta = dict(_META_RE.findall(text))
        key = (meta.get("metric", ""), meta.get("direction", ""))
        body = _META_RE.sub("", text).strip()
        k.docs.setdefault(key, []).append(
            {"doc": md.stem, "section": "", "text": body, "source": meta.get("source", md.name)}
        )

    tpl = root / "templates.json"
    if tpl.exists():
        for t in json.loads(tpl.read_text(encoding="utf-8") or "[]"):
            key = (t.get("metric", ""), t.get("direction", ""))
            k.templates.setdefault(key, []).append({"template_id": t["template_id"], "text": t["text"]})

    seed = root / "sentiment_seed.json"
    if seed.exists():
        data = json.loads(seed.read_text(encoding="utf-8") or "{}")
        for pol in ("pos", "neg"):
            for entry in data.get(pol, []):
                # 문자열이면 term == canonical, {"term","canonical"} 이면 변형 매핑
                if isinstance(entry, str):
                    k.seed_lexicon[entry] = (entry, pol)
                else:
                    k.seed_lexicon[entry["term"]] = (entry.get("canonical", entry["term"]), pol)

    logger.info(
        "knowledge 로드: docs=%d keys, templates=%d keys, seed_lexicon=%d terms",
        len(k.docs), len(k.templates), len(k.seed_lexicon),
    )
    return k
