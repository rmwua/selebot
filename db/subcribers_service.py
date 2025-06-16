class SubscribersService:
    def __init__(self, pool):
        self.pool = pool

    async def add_subscriber(self, chat_id: int) -> None:
        """
        Сохраняет chat_id в таблице, если ещё нет.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO subscribers(chat_id)
                VALUES($1)
                ON CONFLICT (chat_id) DO NOTHING
                """,
                chat_id
            )

    async def get_all_subscribers(self) -> list[int]:
        """
        Возвращает список всех chat_id из subscribers.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id FROM subscribers")
        return [r["chat_id"] for r in rows]