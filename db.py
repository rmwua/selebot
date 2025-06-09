import re
import config
from asyncpg import create_pool
from rapidfuzz import process, fuzz
from unidecode import unidecode

pool = None

def sanitize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text, flags=re.UNICODE).strip().lower()


async def init_db():
    global pool
    pool = await create_pool(dsn=config.DATABASE_URL, min_size=1, max_size=10)


async def get_celeb_by_name(name: str):
    name_clean = name.strip().lower()
    is_ascii   = name_clean.isascii()

    # 1) Загружаем всё в память
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, category, geo, status FROM celebrities")
    celebs = [dict(r) for r in rows]

    if is_ascii:
        # транслитерация и тоже чистим
        translits = [
            sanitize(unidecode(c["name"]))
            for c in celebs
        ]

        # 1) Exact match по транслиту
        for i, t in enumerate(translits):
            if t == name_clean:
                return celebs[i]

        # 2) Substring (подстрока) по транслиту
        for i, t in enumerate(translits):
            if name_clean in t:
                return celebs[i]

        # 3) Fuzzy-partial
        best = process.extractOne(
            name_clean,
            translits,
            scorer=fuzz.partial_ratio,
            score_cutoff=config.FUZY_THRESHOLD
        )
        if best:
            _, _, idx = best
            return celebs[idx]

        # 4) Fuzzy token_sort (ещё один ракурс)
        best = process.extractOne(
            name_clean,
            translits,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=config.FUZY_THRESHOLD
        )
        if best:
            _, _, idx = best
            return celebs[idx]

        # кириллическая ветка

        # 5) Exact по оригинальному имени
    for c in celebs:
        if sanitize(c["name"]) == name_clean:
            return c

        # 6) Substring по оригиналу
    for c in celebs:
        if name_clean in sanitize(c["name"]):
            return c

        # 7) Fuzzy-partial по оригиналу
    names = [sanitize(c["name"]) for c in celebs]
    best = process.extractOne(
        name_clean,
        names,
        scorer=fuzz.partial_ratio,
        score_cutoff=config.FUZY_THRESHOLD
    )
    if best:
        _, _, idx = best
        return celebs[idx]

    # 8) Fuzzy token_sort по оригиналу
    best = process.extractOne(
        name_clean,
        names,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=config.FUZY_THRESHOLD
    )
    if best:
        _, _, idx = best
        return celebs[idx]

    return None


async def find_matching_celebrity(name:str, category: str, geo: str):
    celeb = await get_celeb_by_name(name)
    if celeb and celeb["category"] == category.lower() and celeb["geo"] == geo.lower():
        return celeb
    return None


async def add_pending_request(user_id, chat_id, message_id, celebrity_name, category, geo):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO pending_requests(
              user_id, chat_id, message_id,
              celebrity_name, category, geo
            ) VALUES($1,$2,$3,$4,$5,$6)
            RETURNING id;
            """,
            user_id, chat_id, message_id, celebrity_name, category, geo
        )


async def pop_pending_request(request_id):
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
               geo;
            """,
            request_id
        )


async def insert_celebrity(name: str, category: str, geo: str, status: str):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO celebrities(name, category, geo, status)
            VALUES($1, $2, $3, $4)
            ON CONFLICT (name, category, geo)
            DO UPDATE
               SET status = EXCLUDED.status
            """,
            name, category, geo, status
        )


async def get_categories_by_geo(geo: str) -> list[str]:
    """
    Возвращает список уникальных категорий из таблицы celebrities
    для заданного geo.
    """
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
