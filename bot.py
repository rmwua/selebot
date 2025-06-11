import asyncio
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
import db
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from handlers import (
    cmd_start,
    callback_handler,
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

    async def on_startup():
        subs = await db.get_all_subscribers()
        start_kb = InlineKeyboardMarkup(
        inline_keyboard=[
                [InlineKeyboardButton(text="🚀 START", callback_data="start:from_broadcast")]
            ],
        )
        for chat_id in subs:
            try:
                await bot.send_message(
                    chat_id,
                    "🚀 Бот обновлён до новой версии! Всё готово — нажмите START, чтобы продолжить.",
                    reply_markup=start_kb
                )
            except Exception:
                pass

    async def start_from_broadcast(call: CallbackQuery, state: FSMContext):
        await call.answer()
        await call.message.delete()
        await cmd_start(call.message, state)

    dp.startup.register(on_startup)
    dp.callback_query.register(
        start_from_broadcast,
        F.data == "start:from_broadcast"
    )

    await dp.start_polling(bot, skip_updates=True, on_startup=on_startup)


if __name__ == "__main__":
    asyncio.run(main())
