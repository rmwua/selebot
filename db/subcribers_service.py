from types import NoneType
from typing import Optional


class SubscribersService:
    def __init__(self, pool):
        self.pool = pool


    async def add_subscriber(self, chat_id: int, username: Optional[str] = None) -> int | None:
        """
        Сохраняет chat_id в таблице, если ещё нет.
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO subscribers(chat_id, username)
                    VALUES($1, $2)
                    ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username
                    """,
                    chat_id, username
                )
            return chat_id
        except Exception as e:
            return None


    async def get_all_subscribers(self) -> list[dict]:
        """
        Возвращает список всех chat_id из subscribers.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id, username FROM subscribers")
        return [{"chat_id": r["chat_id"], "username": r["username"]} for r in rows]


    async def get_user(self, chat_id: int) -> dict | None :
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM subscribers WHERE chat_id = $1", chat_id)
            if row:
                return {"chat_id": row["chat_id"], "username": row["username"], "role": row["role"]}
            return None


    async def update_role(self, chat_id: int, new_role: str) -> str | None:
        try:
            async with self.pool.acquire() as conn:
                sql = "UPDATE subscribers SET role = $1 WHERE chat_id = $2"
                await conn.execute(sql, new_role, chat_id)

                return new_role
        except Exception as e:
            return None


    async def get_moderators(self) -> list[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id FROM subscribers WHERE role = 'moderator'")
            return [row['chat_id'] for row in rows]


    async def get_observers(self) -> list[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id FROM subscribers WHERE role = 'observer'")
            return [row['chat_id'] for row in rows]