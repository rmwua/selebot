import asyncio
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from db.celebrity_service import CelebrityService
from db.requests_service import RequestsService
from db.subcribers_service import SubscribersService
from handlers.moderator_handlers import send_request_to_moderator, handle_request_moderator
from keyboards import get_new_search_button, get_geo_keyboard, get_categories_keyboard
from states import SearchMenu

from synonyms import category_synonyms, geo_synonyms
from utils import is_moderator

logger = config.logger


async def cmd_start(message: types.Message, subscribers_service: SubscribersService, state: FSMContext):
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    data = await state.get_data()
    if data.get("started"):
        return

    async def reset_flag():
        await asyncio.sleep(2)
        await state.update_data(started=False)
    asyncio.create_task(reset_flag())

    await state.update_data(started=True)


    await subscribers_service.add_subscriber(message.chat.id, message.from_user.username)

    await message.answer(text="👋 Привет! Я — бот для поиска и согласования селеб."
                              "\n\n🔍 Чтобы начать поиск, отправьте команду"
                              "\n/search"
                              "\n\n❓ Если нужной селебы нет в нашей базе, ваш запрос попадёт к модератору для обработки."
                              "\n\n✅ Также вы можете посмотреть список согласованных селеб командой /approved")


async def cmd_search(message: types.Message, state: FSMContext, subscribers_service: SubscribersService):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔎 По меню", callback_data="mode:menu")
    kb.button(text="✍️ Ручной ввод", callback_data="mode:manual")
    kb.adjust(2)
    await state.clear()
    await state.set_state(SearchMenu.choosing_method)
    await message.answer("Как вы хотите искать?", reply_markup=kb.as_markup())
    if message.text and message.text.startswith('/search'):
            try:
                await message.delete()
            except Exception as e:
                pass

async def mode_chosen(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(":", 1)[1]
    await state.update_data(prompt_message_id=call.message.message_id)

    if mode == "menu":
        geo_kb = get_geo_keyboard()
        await state.set_state(SearchMenu.choosing_geo)
        await call.message.edit_text("Выберите регион:", reply_markup=geo_kb.as_markup())
    else:
        back_button = InlineKeyboardBuilder()
        back_button.button(text="🔙 Назад", callback_data="back:method")
        back_button.adjust(1)
        await state.set_state(SearchMenu.manual_entry)
        await call.message.edit_text("Введите через запятую: Имя, Категория, Гео", reply_markup=back_button.as_markup())
    await call.answer()


async def geo_chosen(call: types.CallbackQuery, state: FSMContext):
    geo_key = call.data.split(":", 1)[1]
    selected_geo = geo_synonyms[geo_key]
    await state.update_data(geo=selected_geo)

    cat_kb = get_categories_keyboard(back_button_callback_data="back:geo")

    await state.set_state(SearchMenu.choosing_cat)
    await call.message.edit_text(
        f"Вы выбрали регион «{selected_geo.title()}». Теперь выберите категорию:",
        reply_markup=cat_kb.as_markup()
    )
    await call.answer()


async def cat_chosen(call: types.CallbackQuery, state: FSMContext):
    cat_key = call.data.split(":", 1)[1]
    await state.update_data(category=cat_key)

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back:cat")
    kb.adjust(1)

    await call.message.edit_text(
        f"Вы выбрали категорию «{cat_key.title()}». Введите теперь имя знаменитости:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(SearchMenu.entering_name)
    await call.answer()


async def name_entered(message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService):
    data = await state.get_data()
    name_input = message.text.strip().lower()
    geo  = data['geo']
    cat  = data['category']

    await handle_request(name_input, cat, geo, message, state, celebrity_service, requests_service)


async def manual_handler(message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService):
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

    await handle_request(name_input, category, geo, message, state, celebrity_service, requests_service)


async def handle_request(name_input: str, category: str, geo: str, message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService):
    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')
    chat_id = message.chat.id
    matched = await celebrity_service.find_celebrity(name_input, category, geo)
    user_id = message.from_user.id
    username = message.from_user.username

    if matched:
        name = matched['name']
        status = matched['status']
        geo = matched['geo']
        raw_cat = matched['category']
        category = raw_cat.strip().lower()
        display_category = 'ЖКТ' if category.lower() == 'жкт' else category.title()

        emoji = "✅" if matched['status'].lower() == 'согласована' else "⛔"

        text = [f"Селеба: {name.title()}\n"
        f"Статус: {status.title()}{emoji}\n"
        f"Категория: {display_category.title()}\n"
        f"Гео: {geo.title()}"]

        show_celebs = False
        if status.lower() == "нельзя использовать":
            text.append("\nВы можете ознакомиться с доступным списком селеб по данному гео/категории:")
            show_celebs = True
            await state.update_data(geo=geo, cat=category)

        kb = get_new_search_button(show_edit_button=True, is_moderator=is_moderator(user_id), show_celebs=show_celebs)
        kb.adjust(1)

        text = "\n".join(text)

        await message.answer(
            text=text,
            reply_markup=kb.as_markup()
        )
        await message.bot.delete_message(chat_id=chat_id, message_id=prompt_id)
    else:
        request_id = await send_request_to_moderator(name_input, category, geo, prompt_id, username, message, requests_service)

        text = f"Ваш запрос в обработке, ожидайте ответа модератора. Номер заявки: {request_id}"

        await message.bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=prompt_id,
            reply_markup=get_new_search_button().as_markup(),
        )


async def available_celebs_handler(call: types.CallbackQuery, celebrity_service: CelebrityService, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    geo = data.get('geo')
    category = data.get('cat')

    celebs = await celebrity_service.get_celebrities(geo, category)
    if celebs:
        text = "<b>Доступные селебы:</b>\n\n" + "\n".join(c.title() for c in celebs)
        await call.message.answer(text, parse_mode="html")
        await call.answer()
    else:
        await call.message.answer("Пока нет согласованных селеб по этому гео и категории. Вы можете отправить заявку модератору через команду /search")
        await call.answer()

    try:
        kb = get_new_search_button()
        await call.message.edit_reply_markup(reply_markup=kb.as_markup())
    except TelegramBadRequest as e:
        pass

async def callback_handler(call: types.CallbackQuery, requests_service: RequestsService, celebrity_service: CelebrityService, state: FSMContext):
    handled = await handle_request_moderator(call, requests_service, celebrity_service)

    name     = handled["name"]
    category = handled["category"]
    geo      = handled["geo"]
    chat_id  = handled["chat_id"]
    msg_id   = handled["message_id"]
    status =  handled["status"]
    prompt_id = handled["prompt_id"]

    emoji = "⛔" if status == "нельзя использовать" else "✅"
    text = [
        f"Статус для `{name.title()}` — *{status}{emoji}*\n"
        f"Категория: {category.title()}\n"
        f"Гео: {geo.title()}"
    ]

    show_celebs = False
    if status == "нельзя использовать":
        show_celebs = True
        text.append("\nВы можете ознакомиться с доступным списком селеб по данному гео/категории:")
        await state.update_data(geo=geo, cat=category)

    kb = get_new_search_button(show_celebs=show_celebs or False)
    text = "\n".join(text)

    await call.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_to_message_id=msg_id,
        reply_markup=kb.as_markup()
    )

    await call.bot.delete_message(chat_id=chat_id, message_id=prompt_id)


async def back_handler(call: types.CallbackQuery, state: FSMContext, subscribers_service: SubscribersService):
    where = call.data.split(":", 1)[1]
    await call.answer()

    if where == "method":
        # back to main menu
        await state.clear()
        await call.message.delete()
        return await cmd_search(call.message, state, subscribers_service)

    if where == "geo":
        # back to choosing geo
        geo_kb = get_geo_keyboard()
        await state.set_state(SearchMenu.choosing_geo)
        return await call.message.edit_text(
            "Выберите регион:",
            reply_markup=geo_kb.as_markup()
        )

    if where == "cat":
        # back to choosing category
        data = await state.get_data()
        geo = data.get("geo")
        cat_kb = get_categories_keyboard(back_button_callback_data="back:geo")

        await state.set_state(SearchMenu.choosing_cat)
        return await call.message.edit_text(
            f"Вы выбрали регион «{geo.title()}». Выберите категорию:",
            reply_markup=cat_kb.as_markup()
        )


async def new_search_handler(call: types.CallbackQuery, state: FSMContext, subscribers_service: SubscribersService):
    await call.answer()
    return await cmd_search(call.message, state, subscribers_service)


async def cmd_approved(message: types.Message, state: FSMContext):
    await message.delete()
    geo_kb = get_geo_keyboard(back_button_callback_data="cancel", back_button_text="Отмена", action_type="geo_approved")
    await state.set_state(SearchMenu.choosing_geo)
    await message.answer("Выберите регион:", reply_markup=geo_kb.as_markup())


async def cancel_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete()
    await state.clear()


async def approved_geo_chosen_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(SearchMenu.choosing_cat)
    geo_key = call.data.split(":", 1)[1]
    selected_geo = geo_synonyms[geo_key]
    await state.update_data(geo=selected_geo)

    cat_kb = get_categories_keyboard(back_button_callback_data="back:approved", action_type="cat_approved")

    await call.message.edit_text(
        f"Вы выбрали регион «{selected_geo.title()}». Теперь выберите категорию:",
        reply_markup=cat_kb.as_markup()
    )


async def back_to_approved_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await cmd_approved(call.message, state)
    await call.message.delete()


async def approved_cat_chosen_handler(call: types.CallbackQuery, state: FSMContext, celebrity_service: CelebrityService):
    await call.answer()
    cat = call.data.split(":", 1)[1]
    await state.update_data(cat=cat)
    await call.message.delete()
    await available_celebs_handler(call, celebrity_service, state)

