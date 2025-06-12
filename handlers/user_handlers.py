from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config, db
from keyboards import get_new_search_button, get_geo_keyboard, get_categories_keyboard
from states import SearchMenu

from synonyms import category_synonyms, geo_synonyms
from utils import is_moderator

logger = config.logger


async def cmd_start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔎 По меню", callback_data="mode:menu")
    kb.button(text="✍️ Ручной ввод", callback_data="mode:manual")
    kb.adjust(2)
    await state.clear()
    await state.set_state(SearchMenu.choosing_method)
    await message.answer("Как вы хотите искать?", reply_markup=kb.as_markup())
    await db.add_subscriber(message.chat.id)


async def mode_chosen(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    back_button = InlineKeyboardBuilder()
    back_button.button(text="🔙 Назад", callback_data="back:method")
    back_button.adjust(1)

    if mode == "menu":
        geo_kb = get_geo_keyboard()
        await state.set_state(SearchMenu.choosing_geo)
        await call.message.edit_text("Выберите регион:", reply_markup=geo_kb.as_markup())
    else:
        await state.set_state(SearchMenu.manual_entry)
        await call.message.edit_text("Введите через запятую: Имя, Категория, Гео", reply_markup=back_button.as_markup())
        await state.update_data(prompt_message_id=call.message.message_id)
    await call.answer()


async def geo_chosen(call: types.CallbackQuery, state: FSMContext):
    geo_key = call.data.split(":", 1)[1]
    selected_geo = geo_synonyms[geo_key]
    await state.update_data(geo=selected_geo)

    cat_kb = get_categories_keyboard(back_button_callback_data="back:geo")

    await state.set_state(SearchMenu.choosing_cat)
    await call.message.edit_text(
        f"Вы выбрали регион «{selected_geo}». Теперь выберите категорию:",
        reply_markup=cat_kb.as_markup()
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
    await state.update_data(prompt_message_id=call.message.message_id)
    await state.set_state(SearchMenu.entering_name)
    await call.answer()


async def name_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name_input = message.text.strip().lower()
    geo  = data['geo']
    cat  = data['category']

    await handle_request(name_input, cat, geo, message, state)


async def manual_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        return await message.answer("Неверный формат. Используйте: Имя, Категория, Гео")

    name_input = parts[0].lower()
    cat_input = parts[1].lower()
    geo_input = parts[2].lower()

    category = category_synonyms.get(cat_input)
    geo = geo_synonyms.get(geo_input)
    new_search_b = get_new_search_button()

    if category is None:
        return await message.answer("Знаменитость не согласована. Данной категории пока нет.", reply_markup=new_search_b.as_markup())
    if geo is None:
        return await message.answer("Знаменитость не согласована. Данного гео пока нет.", reply_markup=new_search_b.as_markup())

    await handle_request(name_input, category, geo, message, state)


async def handle_request(name_input: str, category: str, geo: str, message: types.Message, state: FSMContext):
    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')
    chat_id = message.chat.id
    matched = await db.find_celebrity(name_input, category, geo)
    user_id = message.from_user.id

    if matched:
        name = matched['name']
        status = matched['status']
        geo = matched['geo']
        raw_cat = matched['category']
        category = raw_cat.strip().lower()
        display_category = 'ЖКТ' if category.lower() == 'жкт' else category.title()

        emoji = "✅" if matched['status'].lower() == 'согласована' else "⛔"

        await message.answer(
            f"Селеба: {name.title()}\n"
            f"Статус: {status.title()}{emoji}\n"
            f"Категория: {display_category}\n"
            f"Гео: {geo.title()}",
            reply_markup=get_new_search_button(show_edit_button=True, is_moderator=is_moderator(user_id)).as_markup()
        )
    else:
        request_id = await db.add_pending_request(
            message.from_user.id,
            message.chat.id,
            message.message_id,
            name_input,
            category,
            geo,
            prompt_id
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Одобрить", callback_data=f"approve:{request_id}")
        builder.button(text="⛔ Забанить", callback_data=f"ban:{request_id}")
        builder.adjust(2)

        text = f"Ваш запрос в обработке, ожидайте ответа модератора. Номер заявки: {request_id}"

        await message.bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=prompt_id,
            reply_markup=get_new_search_button().as_markup(),
        )

        await message.bot.send_message(
            config.MODERATOR_ID,
            f"Новая заявка:\nИмя: {name_input}\nКатегория: {category}\nГео: {geo}\nНомер Заявки: {request_id}",
            reply_markup=builder.as_markup()
        )
        await state.clear()


async def callback_handler(call: types.CallbackQuery):
    action, req_id = call.data.split(":", 1)
    is_approve = (action == "approve")
    emoji = "✅" if is_approve else "⛔"

    pending = await db.pop_pending_request(int(req_id))
    if not pending:
        return await call.answer("Заявка не найдена или уже обработана", show_alert=True)

    await call.bot.delete_message(
        chat_id=pending["chat_id"],
        message_id=pending["bot_message_id"]
    )

    name     = pending["celebrity_name"]
    category = pending["category"]
    geo      = pending["geo"]
    chat_id  = pending["chat_id"]
    msg_id   = pending["message_id"]
    status = "Согласована" if is_approve else "Нельзя Использовать"

    new_search_b = get_new_search_button()

    await call.bot.send_message(
        chat_id=chat_id,
        text=(
            f"Статус для `{name.title()}` — *{status}{emoji}*\n"
            f"Категория: {category.title()}\n"
            f"Гео: {geo.title()}"
        ),
        parse_mode="Markdown",
        reply_to_message_id=msg_id,
        reply_markup=new_search_b.as_markup()
    )

    await call.bot.send_message(
        config.MODERATOR_ID,
        f"Заявка #{req_id} на «{name}» обработана: {status}"
    )

    name, category, geo, status = name.lower(), category.lower(), geo.lower(), status.lower()
    await db.insert_celebrity(name, category, geo, status)

    await call.answer("Готово", show_alert=False)
    await call.message.delete()


async def back_handler(call: types.CallbackQuery, state: FSMContext):
    where = call.data.split(":", 1)[1]
    await call.answer()

    if where == "method":
        # возврат в стартовое меню
        await state.clear()
        await call.message.delete()
        return await cmd_start(call.message, state)

    if where == "geo":
        # возврат к выбору регионов
        geo_kb = get_geo_keyboard()
        await state.set_state(SearchMenu.choosing_geo)
        return await call.message.edit_text(
            "Выберите регион:",
            reply_markup=geo_kb.as_markup()
        )

    if where == "cat":
        # возврат к выбору категорий (после того как ввели имя)
        data = await state.get_data()
        geo = data.get("geo")
        cat_kb = get_categories_keyboard(back_button_callback_data="back:geo")

        await state.set_state(SearchMenu.choosing_cat)
        return await call.message.edit_text(
            f"Регион «{geo.title()}». Выберите категорию:",
            reply_markup=cat_kb.as_markup()
        )


async def new_search_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    return await cmd_start(call.message, state)