class RequestsService:
    def __init__(self, pool):
        self.pool = pool

    async def add_pending_request(
            self,
            user_id: int,
            chat_id: int,
            message_id: int,
            celebrity_name: str,
            category: str,
            geo: str,
            bot_message_id: int
    ) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO pending_requests(
                  user_id, chat_id, message_id,
                  celebrity_name, category, geo,
                  bot_message_id
                ) VALUES($1,$2,$3,$4,$5,$6,$7)
                RETURNING id;
                """,
                user_id, chat_id, message_id,
                celebrity_name, category, geo,
                bot_message_id
            )

    async def pop_pending_request(self, request_id: int) -> dict | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                DELETE FROM pending_requests
                 WHERE id = $1
                 RETURNING
                   user_id,
                   chat_id,
                   message_id,
                   celebrity_name,
                   category,
                   geo,
                   bot_message_id;
                """,
                request_id
            )

    async def get_all_pending_requests(self) -> list:
        async with self.pool.acquire() as conn:
            sql = """
            SELECT id, celebrity_name, category, geo, bot_message_id
            FROM pending_requests
            """
            rows = await conn.fetch(sql)
            return rows