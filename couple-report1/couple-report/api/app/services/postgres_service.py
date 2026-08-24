"""PostgreSQL 저장소 인터페이스 자리표시자."""


class PostgresService:
    async def ping(self) -> bool:
        return True

