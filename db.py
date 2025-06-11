import re
from typing import Optional

from unidecode import unidecode

import config
from asyncpg import create_pool, Pool

pool: Optional[Pool] = None


def sanitize_cyr(text: str) -> str:
    # для normalized_name: убираем пунктуацию, оставляем кириллицу
    return re.sub(r"[^\w\s]", "", text, flags=re.UNICODE).strip().lower()

def sanitize_ascii(text: str) -> str:
    # для ascii_name: транслитерируем, потом очищаем
    return re.sub(r"[^\w\s]", "", unidecode(text), flags=re.UNICODE).strip().lower()


async def init_db():
    global pool
    if pool is None:
        pool = await create_pool(dsn=config.DATABASE_URL, min_size=1, max_size=10)


async def find_celebrity(name: str, category: str, geo: str) -> dict | None:
    await init_db()
    assert pool is not None

    # два “нормализованных” варианта ввода
    cyr = sanitize_cyr(name)
    asc = sanitize_ascii(name)
    cat = category.lower()
    loc = geo.lower()

    async with pool.acquire() as conn:
        # 1) exact
        row = await conn.fetchrow(
            """
            SELECT name, category, geo, status
              FROM celebrities
             WHERE lower(category) = $3
               AND lower(geo)      = $4
               AND (
                    normalized_name = $1
                 OR ascii_name      = $2
               )
            """,
            cyr, asc, cat, loc
        )
        if row:
            return dict(row)

        # 2) substring
        row = await conn.fetchrow(
            """
            SELECT name, category, geo, status
              FROM celebrities
             WHERE lower(category) = $3
               AND lower(geo)      = $4
               AND (
                    normalized_name LIKE '%' || $1 || '%'
                 OR ascii_name      LIKE '%' || $2 || '%'
               )
             LIMIT 1
            """,
            cyr, asc, cat, loc
        )
        if row:
            return dict(row)

        # 3) fuzzy via pg_trgm
        row = await conn.fetchrow(
            """
            SELECT name, category, geo, status
              FROM celebrities
             WHERE lower(category) = $3
               AND lower(geo)      = $4
               AND (
                    normalized_name % $1
                 OR ascii_name      % $2
               )
             ORDER BY
               GREATEST(
                 similarity(normalized_name, $1),
                 similarity(ascii_name,      $2)
               ) DESC
             LIMIT 1
            """,
            cyr, asc, cat, loc
        )
        return dict(row) if row else None


async def add_pending_request(
    user_id: int,
    chat_id: int,
    message_id: int,
    celebrity_name: str,
    category: str,
    geo: str,
    bot_message_id: int
) -> int:
    await init_db()
    assert pool is not None
    async with pool.acquire() as conn:
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


async def pop_pending_request(request_id: int) -> dict | None:
    await init_db()
    assert pool is not None
    async with pool.acquire() as conn:
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


async def insert_celebrity(
    name: str,
    category: str,
    geo: str,
    status: str
) -> None:
    """
    Вставляет (или обновляет) селебу, заполняя сразу normalized_name и ascii_name.
    """
    await init_db()
    assert pool is not None

    # вычисляем ascii-транслит на Python
    ascii_val = unidecode(name).lower()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO celebrities
              (name, normalized_name, ascii_name, category, geo, status)
            VALUES
              (
                $1,
                lower(unaccent($1)),  -- normalized_name
                $2,                   -- ascii_name
                $3, $4, $5
              )
            ON CONFLICT (name, category, geo) DO UPDATE
              SET status          = EXCLUDED.status,
                  normalized_name = EXCLUDED.normalized_name,
                  ascii_name      = EXCLUDED.ascii_name;
            """,
            name,       # $1
            ascii_val,  # $2
            category,   # $3
            geo,        # $4
            status      # $5
        )


async def get_categories_by_geo(geo: str) -> list[str]:
    await init_db()
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT category
              FROM celebrities
             WHERE lower(geo) = lower($1)
             ORDER BY category;
            """,
            geo
        )
    return [r["category"] for r in rows]


async def add_subscriber(chat_id: int) -> None:
    """
    Сохраняет chat_id в таблице, если ещё нет.
    """
    await init_db()
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subscribers(chat_id)
            VALUES($1)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            chat_id
        )


async def get_all_subscribers() -> list[int]:
    """
    Возвращает список всех chat_id из subscribers.
    """
    await init_db()
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id FROM subscribers")
    return [r["chat_id"] for r in rows]