from aiogram.filters import Filter
from aiogram import types
from utils import is_admin_or_moderator_or_observer


class AdminModObserverFilter(Filter):
    def __init__(self, subscribers_service):
        self.subscribers_service = subscribers_service

    async def __call__(self, message: types.Message) -> bool:
        user_id = message.from_user.id
        return await is_admin_or_moderator_or_observer(user_id, self.subscribers_service)