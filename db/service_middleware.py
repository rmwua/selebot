from aiogram import BaseMiddleware

from db.celebrity_service import CelebrityService
from db.requests_service import RequestsService
from db.subscribers_service import SubscribersService
from command_manager import CommandManager


class ServiceMiddleware(BaseMiddleware):
    def __init__(self, pool):
        self.pool = pool
        self.celebrity_service = CelebrityService(pool)
        self.requests_service = RequestsService(pool)
        self.subscribers_service = SubscribersService(pool)
        self.command_manager = CommandManager()

    async def __call__(self, handler, event, data):
        data['celebrity_service'] = self.celebrity_service
        data['requests_service'] = self.requests_service
        data['subscribers_service'] = self.subscribers_service
        data['command_manager'] = self.command_manager
        return await handler(event, data)