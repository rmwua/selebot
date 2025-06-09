from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config, db

from synonyms import category_synonyms, geo_synonyms, geo_flags


class RequestCelebrity(StatesGroup):
    waiting_for_info = State()


class SearchMenu(StatesGroup):
    choosing_method = State()
    choosing_geo    = State()
    choosing_cat    = State()
    entering_name   = State()
    manual_entry    = State()


async def cmd_start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔎 По меню", callback_data="mode:menu")
    kb.button(text="✍️ Ручной ввод", callback_data="mode:manual")
    kb.adjust(2)
    await state.clear()
    await state.set_state(SearchMenu.choosing_method)
    await message.answer("Как вы хотите искать?", reply_markup=kb.as_markup())


async def mode_chosen(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    if mode == "menu":
        kb = InlineKeyboardBuilder()
        for key, label in geo_flags.items():
            kb.button(text=label, callback_data=f"geo:{key}")
        kb.adjust(3)

        await state.set_state(SearchMenu.choosing_geo)
        await call.message.edit_text("Выберите регион:", reply_markup=kb.as_markup())
    else:
        await state.set_state(SearchMenu.manual_entry)
        await call.message.edit_text("Введите через запятую: Имя, Категория, Гео")
    await call.answer()


async def geo_chosen(call: types.CallbackQuery, state: FSMContext):
    geo_key = call.data.split(":", 1)[1]
    selected_geo = geo_synonyms[geo_key]
    await state.update_data(geo=selected_geo)

    categories = sorted(set(category_synonyms.values()))

    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.button(text=cat.title(), callback_data=f"cat:{cat}")
    kb.button(text="🔙 Назад", callback_data="back:geo")
    kb.adjust(2)

    await state.set_state(SearchMenu.choosing_cat)
    await call.message.edit_text(
        f"Вы выбрали регион «{selected_geo}». Теперь выберите категорию:",
        reply_markup=kb.as_markup()
    )
    await call.answer()


async def cat_chosen(call: types.CallbackQuery, state: FSMContext):
    cat_key = call.data.split(":", 1)[1]
    await state.update_data(category=cat_key)

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back:cat")
    kb.adjust(1)

    await state.set_state(SearchMenu.entering_name)
    await call.message.edit_text(
        f"Вы выбрали категорию «{cat_key.title()}». Введите теперь имя знаменитости:",
        reply_markup=kb.as_markup()
    )
    await call.answer()


async def name_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name_input = message.text.strip().lower()
    geo  = data['geo']
    cat  = data['category']

    celeb = await db.find_matching_celebrity(name_input, cat, geo)
    if celeb:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Новый поиск", callback_data="new_search")
        keyboard = kb.as_markup()

        await message.answer(
            f"Селеба: {celeb['name']}\n"
            f"Статус: {celeb['status']}\n"
            f"Категория: {celeb['category']}\n"
            f"Гео: {celeb['geo']}",
            reply_markup=keyboard
        )
    else:
        request_id = await db.add_pending_request(
            message.from_user.id,
            message.chat.id,
            message.message_id,
            name_input,
            cat,
            geo
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Одобрить", callback_data=f"approve:{request_id}")
        builder.button(text="⛔ Забанить", callback_data=f"ban:{request_id}")
        builder.adjust(2)
        keyboard = builder.as_markup()

        await message.answer("Ваш запрос в обработке, ожидайте ответа модератора…")

        await message.bot.send_message(
            config.MODERATOR_ID,
            (
                f"Новая заявка (через меню):\n"
                f"Имя: {name_input}\n"
                f"Категория: {cat}\n"
                f"Гео: {geo}\n"
                f"Request ID: {request_id}"
            ),
            reply_markup=keyboard
        )

    await state.clear()



async def manual_handler(message: types.Message, state: FSMContext):
    await handle_request(message, state)
    await state.clear()


async def handle_request(message: types.Message, state: FSMContext):
    text = message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        return await message.answer("Неверный формат. Используйте: Имя, Категория, Гео")

    name_input = parts[0].lower()
    cat_input = parts[1].lower()
    geo_input = parts[2].lower()

    category = category_synonyms.get(cat_input)
    geo = geo_synonyms.get(geo_input)

    if category is None:
        return await message.answer("Знаменитость не согласована. Данной категории пока нет.")
    if geo is None:
        return await message.answer("Знаменитость не согласована. Данного гео пока нет.")

    matched = await db.find_matching_celebrity(name_input, category, geo)
    if matched:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Новый поиск", callback_data="new_search")
        keyboard = kb.as_markup()

        await message.answer(
            f"Селеба: {matched['name']}\n"
            f"Статус: {matched['status']}\n"
            f"Категория: {matched['category']}\n"
            f"Гео: {matched['geo']}",
            reply_markup=keyboard
        )
    else:
        request_id = await db.add_pending_request(
            message.from_user.id,
            message.chat.id,
            message.message_id,
            name_input,
            category,
            geo
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Одобрить", callback_data=f"approve:{request_id}")
        builder.button(text="⛔ Забанить", callback_data=f"ban:{request_id}")
        builder.adjust(2)
        keyboard = builder.as_markup()

        await message.answer("Ваш запрос в обработке, ожидайте ответа модератора…")
        await message.bot.send_message(
            config.MODERATOR_ID,
            f"Новая заявка:\nИмя: {name_input}\nКатегория: {category}\nГео: {geo}\nRequest ID: {request_id}",
            reply_markup=keyboard
        )
        await state.clear()
        return await cmd_start(message, state)


async def callback_handler(call: types.CallbackQuery):
    action, req_id = call.data.split(":", 1)
    is_approve = (action == "approve")

    pending = await db.pop_pending_request(int(req_id))
    if not pending:
        return await call.answer("Заявка не найдена или уже обработана", show_alert=True)

    name     = pending["celebrity_name"]
    category = pending["category"]
    geo      = pending["geo"]
    chat_id  = pending["chat_id"]
    msg_id   = pending["message_id"]

    status = "Согласована" if is_approve else "Черный список"

    await db.insert_celebrity(name, category, geo, status)

    await call.bot.send_message(
        chat_id,
        f"Статус для `{name}` — *{status}*",
        parse_mode="Markdown",
        reply_to_message_id=msg_id
    )

    await call.bot.send_message(
        config.MODERATOR_ID,
        f"Заявка #{req_id} на «{name}» обработана: {status}"
    )

    await call.answer("Готово", show_alert=False)
    await call.message.delete()


async def back_handler(call: types.CallbackQuery, state: FSMContext):
    where = call.data.split(":", 1)[1]
    await call.answer()

    if where == "method":
        # возврат в стартовое меню
        await state.clear()
        return await cmd_start(call.message, state)

    if where == "geo":
        # возврат к выбору регионов
        kb = InlineKeyboardBuilder()
        for key, label in geo_flags.items():
            kb.button(text=label, callback_data=f"geo:{key}")
        kb.adjust(3)
        await state.set_state(SearchMenu.choosing_geo)
        return await call.message.edit_text(
            "Выберите регион:",
            reply_markup=kb.as_markup()
        )

    if where == "cat":
        # возврат к выбору категорий (после того как ввели имя)
        data = await state.get_data()
        geo = data.get("geo")
        categories = sorted(set(category_synonyms.values()))
        kb = InlineKeyboardBuilder()
        for cat in categories:
            kb.button(text=cat.title(), callback_data=f"cat:{cat}")
        kb.button(text="🔙 Назад", callback_data="back:method")
        kb.adjust(2)

        await state.set_state(SearchMenu.choosing_cat)
        return await call.message.edit_text(
            f"Регион «{geo}». Выберите категорию:",
            reply_markup=kb.as_markup()
        )


async def new_search_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    return await cmd_start(call.message, state)