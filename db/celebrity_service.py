from typing import Dict, Any

from utils import sanitize_cyr, sanitize_ascii


class CelebrityService:
    def __init__(self, pool):
        self.pool = pool

    async def find_celebrity(self, name: str, category: str, geo: str) -> dict | None:
        cyr = sanitize_cyr(name)
        asc = sanitize_ascii(name)
        cat = category.lower()
        loc = geo.lower()
        MIN_SIMILARITY = 0.6

        async with self.pool.acquire() as conn:
            # 1) exact
            row = await conn.fetchrow(
                """
                SELECT id, name, category, geo, status
                  FROM celebrities
                 WHERE lower(category) = $1
                   AND lower(geo)      = $2
                   AND (
                        normalized_name = $3
                     OR ascii_name      = $4
                   )
                """,
                cat, loc, cyr, asc
            )
            if row:
                return dict(row)

            # 2) substring
            row = await conn.fetchrow(
                """
                SELECT id, name, category, geo, status
                  FROM celebrities
                 WHERE lower(category) = $1
                   AND lower(geo)      = $2
                   AND (
                        normalized_name LIKE '%' || $3 || '%'
                     OR ascii_name      LIKE '%' || $4 || '%'
                   )
                 LIMIT 1
                """,
                cat, loc, cyr, asc
            )
            if row:
                return dict(row)

            # 3) fuzzy via pg_trgm
            row = await conn.fetchrow(
                """
                SELECT id, name, category, geo, status
                  FROM celebrities
                 WHERE lower(category) = $1
                   AND lower(geo)      = $2
                   -- % оставляем, чтобы быстро отсечь совсем чужие записи,
                   -- но дополнительно проверяем similarity > MIN_SIMILARITY
                   AND (
                        normalized_name % $3
                     OR ascii_name      % $4
                   )
                   AND (
                        similarity(normalized_name, $3) > $5
                     OR similarity(ascii_name,      $4) > $5
                   )
                 ORDER BY
                   GREATEST(
                     similarity(normalized_name, $3),
                     similarity(ascii_name,      $4)
                   ) DESC
                 LIMIT 1
                """,
                cat, loc, cyr, asc, MIN_SIMILARITY
            )
            return dict(row) if row else None

    async def insert_celebrity(self, name: str, category: str, geo: str, status: str) -> dict:
        """
        Вставляет (или обновляет) селебу, заполняя сразу normalized_name и ascii_name.
        """
        ascii_val = sanitize_ascii(name)
        cyr_name = sanitize_cyr(name)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO celebrities
                  (name, normalized_name, ascii_name, category, geo, status)
                VALUES
                  (
                    $1,
                    $2,  -- normalized_name
                    $3,  -- ascii_name
                    $4, $5, $6
                  )
                ON CONFLICT (name, category, geo) DO UPDATE
                  SET status          = EXCLUDED.status,
                      normalized_name = EXCLUDED.normalized_name,
                      ascii_name      = EXCLUDED.ascii_name
                RETURNING id, name, category, geo, status;
                """,
                name, cyr_name, ascii_val, category, geo, status
            )
            return dict(row)

    async def get_celebrities(self, geo:str , cat: str) -> list[str] | None:
        async with self.pool.acquire() as conn:
            sql = """
            SELECT DISTINCT name 
            FROM celebrities
            WHERE category = lower($1) AND geo = lower($2) AND status = 'согласована';
            """
            params = [cat, geo]
            rows = await conn.fetch(sql, *params)
            return [row['name'] for row in rows]

    async def get_categories_by_geo(self, geo: str) -> list[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT category
                  FROM celebrities
                 WHERE geo = lower($1)
                 ORDER BY category;
                """,
                geo
            )
        return [r["category"] for r in rows]


    async def update_celebrity(self, name: str, geo: str, category: str, status: str, new_name=None, new_geo=None,
                               new_cat=None, new_status=None) -> dict[Any, Any]:
        updates = {}
        if new_name:
            updates["name"] = new_name.lower()
            updates["normalized_name"] = sanitize_cyr(new_name)
            updates["ascii_name"] = sanitize_ascii(new_name)
        if new_cat:
            updates["category"] = new_cat.lower()
        if new_geo:
            updates["geo"] = new_geo.lower()
        if new_status:
            updates["status"] = new_status.lower()

        set_clauses = []
        set_values = []
        for i, (col, val) in enumerate(updates.items(), start=1):
            set_clauses.append(f"{col} = ${i}")
            set_values.append(val.lower())
        set_sql = ", ".join(set_clauses)

        where_values = [name, geo, category]
        idx = len(set_values)
        where_sql = (
            f"lower(name) = lower(${idx+1}) "
            f"AND lower(geo) = lower(${idx+2}) "
            f"AND lower(category) = lower(${idx+3})"
        )

        query = f"""
            UPDATE celebrities
            SET {set_sql}
            WHERE {where_sql}
            RETURNING id, name, category, geo, status;
        """

        params = set_values + where_values

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row)

    async def delete_celebrity(self, name: str, geo: str, category: str, status: str) -> None:

        query = """
        DELETE FROM celebrities
        WHERE name = $1 AND category = $2 AND geo = $3;
        """

        params = [name, category, geo]
        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)

    async def update_by_id(self, rec_id: int, *, name: str, category: str, geo: str, status: str) -> dict:
        """
        Обновляет запись по её id. Пересчитывает normalized_name и ascii_name.
        """
        ascii_val = sanitize_ascii(name)
        cyr_name  = sanitize_cyr(name)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE celebrities
                   SET name            = $2,
                       normalized_name = $3,
                       ascii_name      = $4,
                       category        = $5,
                       geo             = $6,
                       status          = $7
                 WHERE id = $1
                RETURNING id, name, category, geo, status;
                """,
                rec_id, name, cyr_name, ascii_val, category, geo, status
            )
            if not row:
                raise ValueError(f"No celebrity with id={rec_id}")
            return dict(row)

    async def delete_by_id(self, rec_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM celebrities WHERE id = $1", rec_id)