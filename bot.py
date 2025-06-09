import asyncio

import config
import db

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from handlers import (
    cmd_start,
    handle_request,
    callback_handler,
    RequestCelebrity,
    mode_chosen,
    geo_chosen,
    cat_chosen,
    name_entered,
    SearchMenu,
    manual_handler, back_handler, new_search_handler,
)


async def main():
    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(
        cmd_start,
        Command("start"),
    )

    dp.message.register(
        handle_request,
        StateFilter(RequestCelebrity.waiting_for_info),
    )

    dp.callback_query.register(
        mode_chosen,
        F.data.startswith("mode:"),
        StateFilter(SearchMenu.choosing_method),
    )

    dp.callback_query.register(
        geo_chosen,
        F.data.startswith("geo:"),
        StateFilter(SearchMenu.choosing_geo),
    )

    dp.callback_query.register(
        cat_chosen,
        F.data.startswith("cat:"),
        StateFilter(SearchMenu.choosing_cat),
    )

    dp.message.register(
        name_entered,
        StateFilter(SearchMenu.entering_name),
    )

    dp.message.register(
        manual_handler,
        StateFilter(SearchMenu.manual_entry),
    )

    dp.callback_query.register(
        callback_handler,
        F.data.startswith("approve:") | F.data.startswith("ban:"),
    )

    dp.callback_query.register(
        back_handler,
        F.data.startswith("back:"),
    )

    dp.callback_query.register(
        new_search_handler,
        F.data == "new_search"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
