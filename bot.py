import asyncio
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
import config
from aiogram import types
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter

from db.celebrity_service import CelebrityService
from db.database_manager import DatabaseManager
from db.requests_service import RequestsService
from db.service_middleware import ServiceMiddleware
from db.subcribers_service import SubscribersService
from handlers.moderator_handlers import edit_handler, field_chosen, name_edited, edit_back_button_handler, \
    new_param_chosen, delete_celebrity_handler, delete_request_handler, cmd_requests, cmd_users
from handlers.user_handlers import (
    cmd_search, cmd_start,
    callback_handler,
    mode_chosen,
    geo_chosen,
    cat_chosen,
    name_entered,
    SearchMenu,
    manual_handler, back_handler, new_search_handler, available_celebs_handler, cmd_approved, cancel_handler,
    approved_geo_chosen_handler, back_to_approved_handler, approved_cat_chosen_handler,
)
from states import EditCelebrity


async def main():
    pool = await DatabaseManager.get_pool()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.update.middleware(ServiceMiddleware(pool))

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_search, Command("search"))
    dp.message.register(cmd_approved, Command("approved"))
    dp.message.register(cmd_requests, Command("requests"), F.from_user.id == config.MODERATOR_ID)
    dp.message.register(cmd_users, Command("users"), F.from_user.id == config.MODERATOR_ID)
    dp.message.register(lambda message: message.answer(f"❌ У вас нет прав для этой команды."),Command("requests"))
    dp.message.register(lambda message: message.answer(f"❌ У вас нет прав для этой команды."), Command("users"))

    dp.message.register(name_entered, StateFilter(SearchMenu.entering_name))
    dp.message.register(manual_handler, StateFilter(SearchMenu.manual_entry))

    dp.callback_query.register(mode_chosen, F.data.startswith("mode:"), StateFilter(SearchMenu.choosing_method))
    dp.callback_query.register(geo_chosen, F.data.startswith("geo:"), StateFilter(SearchMenu.choosing_geo))
    dp.callback_query.register(cat_chosen, F.data.startswith("cat:"), StateFilter(SearchMenu.choosing_cat))
    dp.callback_query.register(available_celebs_handler, F.data == "available_celebs")

    dp.callback_query.register(callback_handler, F.data.startswith("approve:") | F.data.startswith("ban:"))
    dp.callback_query.register(back_to_approved_handler, F.data == "back:approved", StateFilter(SearchMenu.choosing_cat))
    dp.callback_query.register(back_handler,F.data.startswith("back:"))
    dp.callback_query.register(new_search_handler,F.data == "new_search")

    dp.callback_query.register(edit_handler, F.data == "edit")
    dp.callback_query.register(field_chosen, F.data.startswith("edit_field:"), StateFilter(EditCelebrity.choosing_field))
    dp.message.register(name_edited, StateFilter(EditCelebrity.editing_name))
    dp.callback_query.register(edit_back_button_handler, F.data == "edit:back")
    dp.callback_query.register(new_param_chosen, F.data.startswith("edit_cat:") | F.data.startswith("edit_geo:") | F.data.startswith("edit_status"),StateFilter(EditCelebrity.editing_param))
    dp.callback_query.register(delete_celebrity_handler, F.data == "edit:delete", StateFilter(EditCelebrity.deleting_entry))

    dp.callback_query.register(approved_geo_chosen_handler, F.data.startswith("geo_approved"), StateFilter(SearchMenu.choosing_geo))
    dp.callback_query.register(approved_cat_chosen_handler, F.data.startswith("cat_approved"))
    dp.callback_query.register(cancel_handler, F.data == "cancel")

    dp.callback_query.register(delete_request_handler, F.data.startswith("delete:"))

    async def on_startup():
        await DatabaseManager.init()

        dp['pool'] = pool

        dp['celebrity_service'] = CelebrityService(pool)
        dp['requests_service'] = RequestsService(pool)
        dp['subscribers_service'] = SubscribersService(pool)

        common_commands = [
            types.BotCommand(command="start", description="Инфо о боте"),
            types.BotCommand(command="search", description="Новый поиск/Заявка модератору"),
            types.BotCommand(command="approved", description="Список согласованных селеб")
        ]
        mod_commands = common_commands + [types.BotCommand(command="requests", description="Посмотреть активные заявки "),
                                          types.BotCommand(command="users", description="Посмотреть кто подписан на бота")]

        await bot.set_my_commands(mod_commands, scope=types.BotCommandScopeChat(chat_id=config.MODERATOR_ID))
        await bot.set_my_commands(common_commands)

        # send message to all subscribers on update
        # subs = await dp['subscribers_service'].get_all_subscribers()
        # start_kb = InlineKeyboardMarkup(
        # inline_keyboard=[
        #         [InlineKeyboardButton(text="🚀 START", callback_data="start:from_broadcast")]
        #     ],
        # )
        # for chat_id in subs:
        #     try:
        #         await bot.send_message(
        #             chat_id,
        #             "🚀 Бот обновлён до новой версии! Всё готово — нажмите START, чтобы продолжить.",
        #             reply_markup=start_kb
        #         )
        #     except Exception:
        #         pass


    async def on_shutdown():
        await pool.close()
    #
    #
    # async def start_from_broadcast(call: CallbackQuery, state: FSMContext):
    #     await call.answer()
    #     await cmd_start(call.message, state, dp['subscribers_service'])


    dp.startup.register(on_startup)
    # dp.callback_query.register(
    #     start_from_broadcast,
    #     F.data == "start:from_broadcast"
    # )
    await dp.start_polling(bot, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)


if __name__ == "__main__":
    asyncio.run(main())
