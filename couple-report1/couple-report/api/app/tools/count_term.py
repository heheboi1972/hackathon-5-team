"""API_SPEC §8 count_term 도구 Mock."""


async def count_term(term: str, *_: object, **__: object) -> dict[str, object]:
    return {"term": term, "total": 0, "matched_forms": [], "by_week": []}

