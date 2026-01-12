from aiogram import Bot, types
from config import ADMIN_ID, logger  # если нужно

class CommandManager:
    def __init__(self):
        self.common = [
            types.BotCommand(command="start", description="Инфо о боте"),
            types.BotCommand(command="search", description="Новый поиск/Заявка модератору"),
            types.BotCommand(command="approved", description="Список согласованных селеб")
        ]

        self.admin = self.common + [
            types.BotCommand(command="requests", description="Посмотреть активные заявки "),
            types.BotCommand(command="users", description="Посмотреть кто подписан на бота"),
            types.BotCommand(command="role", description="Редактирование роли юзера"),
            types.BotCommand(command="upload", description="Выгрузить из бд в таблицу")
        ]

        self.mod_observer = self.common + [
            types.BotCommand(command="requests", description="Посмотреть активные заявки")
        ]

    def get_commands_for_role(self, role: str) -> list[types.BotCommand]:
        if role == "admin":
            return self.admin
        elif role in ("moderator", "observer"):
            return self.mod_observer
        else:
            return self.common

    async def set_commands_for_user(self, bot: Bot, user_id: int, role: str):
        commands = self.get_commands_for_role(role)
        try:
            await bot.set_my_commands(commands, scope=types.BotCommandScopeChat(chat_id=user_id))
        except Exception as e:
            logger.error(f"Не удалось установить команды для {user_id}: {e}")

    async def set_global_commands(self, bot: Bot):
        await bot.set_my_commands(self.common)

    async def set_admin_commands(self, bot: Bot, admin_id: int = ADMIN_ID):
        await bot.set_my_commands(self.admin, scope=types.BotCommandScopeChat(chat_id=admin_id))
