"""API_SPEC §8 get_metrics 도구 Mock."""


async def get_metrics(*_: object, **__: object) -> dict[str, object]:
    return {"summary": {}, "metrics": {}}

