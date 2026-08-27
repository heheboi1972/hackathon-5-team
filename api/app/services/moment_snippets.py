"""Hydrate report moments with short, authorized message excerpts."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
SNIPPET_MAX_CHARS = 150


def _snippet(body: str) -> str:
    compact = " ".join(body.split())
    return compact if len(compact) <= SNIPPET_MAX_CHARS else compact[:SNIPPET_MAX_CHARS] + "…"


def hydrate_moment_snippets(
    moments: list[dict[str, Any]], rows: list[dict[str, Any]], decrypt: Any
) -> list[dict[str, Any]]:
    """Attach the message nearest each moment timestamp without persisting plaintext."""
    by_session: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("session_id") is not None:
            by_session[int(row["session_id"])].append(row)

    hydrated: list[dict[str, Any]] = []
    for original in moments:
        moment = dict(original)
        moment.pop("snippet", None)
        try:
            at = moment.get("at")
            target = at if isinstance(at, datetime) else datetime.fromisoformat(str(at))
            candidates = by_session.get(int(moment["session_id"]), [])
            if candidates:
                nearest = min(candidates, key=lambda row: abs((row["sent_at"] - target).total_seconds()))
                snippet = _snippet(decrypt(nearest["body_enc"]))
                if snippet:
                    moment["snippet"] = snippet
        except (KeyError, TypeError, ValueError, OverflowError):
            logger.warning(
                "Could not hydrate report moment snippet session_id=%s",
                moment.get("session_id"),
                exc_info=True,
            )
        hydrated.append(moment)
    return hydrated
