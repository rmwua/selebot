from aiogram import BaseMiddleware

from db.celebrity_service import CelebrityService
from db.requests_service import RequestsService
from db.subcribers_service import SubscribersService


class ServiceMiddleware(BaseMiddleware):
    def __init__(self, pool):
        self.pool = pool
        self.celebrity_service = CelebrityService(pool)
        self.requests_service = RequestsService(pool)
        self.subscribers_service = SubscribersService(pool)

    async def __call__(self, handler, event, data):
        data['celebrity_service'] = self.celebrity_service
        data['requests_service'] = self.requests_service
        data['subscribers_service'] = self.subscribers_service
        return await handler(event, data)