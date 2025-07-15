import asyncio
import config
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter

from db.celebrity_service import CelebrityService
from db.database_manager import DatabaseManager
from db.requests_service import RequestsService
from db.service_middleware import ServiceMiddleware
from db.subcribers_service import SubscribersService
from filters import AdminModObserverFilter
from handlers.moderator_handlers import edit_handler, field_chosen, name_edited, edit_back_button_handler, \
    new_param_chosen, delete_celebrity_handler, delete_request_handler, cmd_requests, cmd_users, cmd_role, \
    cancel_role_handler, cmd_role_receive_user_id, resume_role_changing_handler, role_chosen_handler
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
from states import EditCelebrity, EditUserRole
from command_manager import CommandManager


def create_on_startup(dp: Dispatcher, bot: Bot):
    async def on_startup():
        pool = dp['pool']
        dp['celebrity_service'] = CelebrityService(pool)
        dp['requests_service'] = RequestsService(pool)
        dp['subscribers_service'] = SubscribersService(pool)
        command_manager = CommandManager()

        moderators = await dp['subscribers_service'].get_moderators()
        observers = await dp['subscribers_service'].get_observers()
        extra_users = moderators + observers

        for user_id in extra_users:
            role = await dp['subscribers_service'].get_user_role(user_id)
            await command_manager.set_commands_for_user(bot, user_id, role)

        await command_manager.set_admin_commands(bot)
        await command_manager.set_global_commands(bot)

    return on_startup

async def on_shutdown():
    await DatabaseManager.close()


async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    await DatabaseManager.init()
    pool = await DatabaseManager.get_pool()
    dp.update.middleware(ServiceMiddleware(pool))
    dp['pool'] = pool
    subscribers_service = SubscribersService(pool)
    admin_mod_observer_filter = AdminModObserverFilter(subscribers_service)

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_search, Command("search"))
    dp.message.register(cmd_approved, Command("approved"))
    dp.message.register(cmd_requests, Command("requests"), admin_mod_observer_filter)
    dp.message.register(cmd_users, Command("users"), F.from_user.id == config.ADMIN_ID)
    dp.message.register(lambda message: message.answer(f"❌ У вас нет прав для этой команды."),Command("requests"), ~admin_mod_observer_filter)
    dp.message.register(lambda message: message.answer(f"❌ У вас нет прав для этой команды."), Command("users"))
    dp.message.register(cmd_role, Command("role"), F.from_user.id == config.ADMIN_ID)
    dp.message.register(lambda message: message.answer(f"❌ У вас нет прав для этой команды."), Command("role"))

    dp.callback_query.register(cancel_role_handler, F.data == "cancel_role_change")
    dp.callback_query.register(resume_role_changing_handler, F.data == "resume_role_changing")
    dp.callback_query.register(role_chosen_handler, F.data.startswith("role_set:"), StateFilter(EditUserRole.waiting_for_role_choice))
    dp.message.register(cmd_role_receive_user_id, StateFilter(EditUserRole.waiting_for_id))


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


    dp.startup.register(create_on_startup(dp, bot))
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
