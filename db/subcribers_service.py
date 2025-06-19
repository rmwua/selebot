from typing import Tuple, List


class SubscribersService:
    def __init__(self, pool):
        self.pool = pool

    async def add_subscriber(self, chat_id: int, username:str) -> None:
        """
        Сохраняет chat_id в таблице, если ещё нет.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO subscribers(chat_id, username)
                VALUES($1, $2)
                ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username
                """,
                chat_id, username
            )

    async def get_all_subscribers(self) -> list[dict]:
        """
        Возвращает список всех chat_id из subscribers.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id, username FROM subscribers")
        return [{"chat_id": r["chat_id"], "username": r["username"]} for r in rows]