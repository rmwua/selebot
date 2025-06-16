from asyncpg import create_pool, Pool
import config


class DatabaseManager:
    _pool: Pool = None

    @classmethod
    async def init(cls):
        if cls._pool is None:
            cls._pool = await create_pool(
                dsn=config.DATABASE_URL,
                min_size=1,
                max_size=10
            )

    @classmethod
    async def get_pool(cls) -> Pool:
        if cls._pool is None:
            await cls.init()
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None