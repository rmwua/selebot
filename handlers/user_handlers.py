import asyncio
from aiogram import types, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from command_manager import CommandManager
from db.celebrity_service import CelebrityService
from db.requests_service import RequestsService
from db.subscribers_service import SubscribersService
from handlers.moderator_handlers import send_request_to_moderator, handle_request_moderator
from keyboards import get_new_search_button, get_geo_keyboard, get_categories_keyboard
from states import SearchMenu

from synonyms import category_synonyms, geo_synonyms
from utils import is_moderator, split_names

logger = config.logger


def build_card_text(celeb: dict) -> str:
    name = celeb["name"]
    status = celeb["status"]
    geo = celeb["geo"]
    raw_cat = celeb["category"]
    category = raw_cat.strip().lower()
    display_category = "ЖКТ" if category == "жкт" else category.title()
    emoji = "✅" if status.lower() == "согласована" else "⛔"
    return "\n".join([
        f"Селеба: {name.title()}",
        f"Статус: {status.title()}{emoji}",
        f"Категория: {display_category}",
        f"Гео: {geo.title()}",
    ])


async def cmd_start(message: types.Message, subscribers_service: SubscribersService, state: FSMContext, command_manager: CommandManager, bot:Bot):
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    data = await state.get_data()
    if data.get("started"):
        return
    user_id = message.from_user.id

    async def reset_flag():
        await asyncio.sleep(2)
        await state.clear()

    asyncio.create_task(reset_flag())
    await state.update_data(started=True)
    await subscribers_service.add_subscriber(message.chat.id, message.from_user.username)

    user_role = await subscribers_service.get_user_role(user_id)
    logger.info(f"USER ROLE: {user_role}")
    await command_manager.set_commands_for_user(bot, user_id, user_role)

    await message.answer(text="👋 Привет! Я — бот для поиска и согласования селеб."
                              "\n\n🔍 Чтобы начать поиск, отправьте команду"
                              "\n/search"
                              "\n\n❓ Если нужной селебы нет в нашей базе, ваш запрос попадёт к модератору для обработки."
                              "\n\n✅ Также вы можете посмотреть список согласованных селеб командой /approved"
                              "\n\n💡 Массовый поиск (несколько имён)"
                                "\n 1) /search → «По меню» → выберите регион и категорию."
                                "\n 2) Введите сразу несколько имён через запятую, точку с запятой или с новой строки."
                                "\n\nПример:"
                                 "\nTomira Kowalik, Joanna Kotaczkowska, Krystyna Janda"
                                "\n\nВ ответ придёт одно сообщение-сводка"
                         )


async def cmd_search(message: types.Message, state: FSMContext):
    await state.clear()
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


async def name_entered(message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService, subscribers_service: SubscribersService):
    data = await state.get_data()
    geo  = data['geo']
    cat  = data['category']
    names = split_names(message.text)
    if len(names) == 1:
        name_input = names[0]
        return await handle_request(name_input, cat, geo, message, state, celebrity_service, requests_service, subscribers_service)
    return await handle_batch_request(names, cat, geo, message, state, celebrity_service, requests_service, subscribers_service)


async def manual_handler(message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService, subscribers_service: SubscribersService):
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

    await handle_request(name_input, category, geo, message, state, celebrity_service, requests_service, subscribers_service)


async def handle_batch_request(names: list, category: str, geo: str, message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService, subscribers_service: SubscribersService):
    found: list[dict] = []
    not_found: list[dict] = []
    ambiguous: list[dict] = []

    batch_similar_map: dict[int, list[dict]] = {}
    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')
    chat_id = message.chat.id

    for idx, name in enumerate(names):
        matched = await celebrity_service.find_celebrity(name, category, geo)
        if isinstance(matched, dict):
            found.append({"query": name, "rec": matched})
        elif isinstance(matched, list):
            first = matched[0]
            ambiguous.append({"idx": idx, "query": name, "first": first, "all": matched})
            batch_similar_map[idx] = matched
        else:
            not_found.append({"query": name, "rec": matched})

    text = (f"Гео: {geo.title()}\n"
            f"Категория: {category.title()}\n")

    def _format_item_line(item: dict) -> str:
        rec = item.get("rec") or item.get("first")
        if not rec:
            return ""
        status = (rec.get("status") or "")
        emoji = "⛔" if status.lower() == "нельзя использовать" else "✅"
        return f"\n{rec['name'].title()} - {status}{emoji}"

    for item in (found + ambiguous):
        text += _format_item_line(item)

    for item in not_found:
        name_input = item["query"]
        prompt_id = data.get('prompt_message_id')
        username = message.from_user.username

        request_id = await send_request_to_moderator(name_input, category, geo, prompt_id, username, message,requests_service, subscribers_service)
        item_text = f"\n{name_input.title()} - Отправлен запрос модератору 🟡 Номер заявки: {request_id}"
        text += item_text

    kb = get_new_search_button()
    await message.answer(text=text, reply_markup=kb.as_markup())


async def handle_request(name_input: str, category: str, geo: str, message: types.Message, state: FSMContext, celebrity_service: CelebrityService, requests_service: RequestsService, subscribers_service: SubscribersService):
    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')
    chat_id = message.chat.id
    matched = await celebrity_service.find_celebrity(name_input, category, geo)
    user_id = message.from_user.id
    username = message.from_user.username
    similar = False

    if isinstance(matched, list):
        if not matched:
            matched = None
        else:
            similar_list = matched
            matched = matched[0]
            similar = True
            await state.update_data(query_name=name_input, cat=category, geo=geo, similar_list=similar_list, initial_celeb_id=matched["id"])

    if matched is None:
        request_id = await send_request_to_moderator(name_input, category, geo, prompt_id, username, message, requests_service, subscribers_service)

        text = f"Ваш запрос в обработке, ожидайте ответа модератора. Номер заявки: {request_id}"

        await message.bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=prompt_id,
            reply_markup=get_new_search_button().as_markup(),
        )
        return

    status = matched['status']
    geo = matched['geo']
    raw_cat = matched['category']
    celeb_id = matched['id']
    category = raw_cat.strip().lower()

    text = [build_card_text(matched)]

    await state.update_data(celeb_id=celeb_id)

    show_celebs = False
    if status.lower() == "нельзя использовать":
        text.append("\nВы можете ознакомиться с доступным списком селеб по данному гео/категории:")
        show_celebs = True
        await state.update_data(geo=geo, cat=category)

    kb = get_new_search_button(show_edit_button=True, is_moderator=is_moderator(user_id), show_celebs=show_celebs, similar=similar)
    kb.adjust(1)

    text = "\n".join(text)

    await message.answer(
        text=text,
        reply_markup=kb.as_markup()
    )
    try:
        await message.bot.delete_message(chat_id=chat_id, message_id=prompt_id)
    except TelegramBadRequest:
        pass


async def available_celebs_handler(call: types.CallbackQuery, celebrity_service: CelebrityService, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    geo = data.get('geo')
    category = data.get('cat')

    celebs = await celebrity_service.get_celebrities(geo, category)
    if celebs:
        text = f"<b>Доступные селебы на {geo.title()}/{category.title()}:</b>\n\n" + "\n".join(c.title() for c in celebs)
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
    if not isinstance(handled, dict):
        return

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

    try:
        await call.bot.delete_message(chat_id=chat_id, message_id=prompt_id)
    except TelegramBadRequest as e:
        logger.error(e)


async def back_handler(call: types.CallbackQuery, state: FSMContext):
    where = call.data.split(":", 1)[1]
    await call.answer()

    if where == "method":
        # back to main menu
        await state.clear()
        await call.message.delete()
        return await cmd_search(call.message, state)

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


async def new_search_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    return await cmd_search(call.message, state)


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


async def similar_celebs_handler(call: types.CallbackQuery, state: FSMContext, requests_service: RequestsService, subscribers_service: SubscribersService):
    await call.answer()
    data = await state.get_data()
    similar_list = data.get("similar_list") or []
    initial_celeb_id = data.get("initial_celeb_id")

    if not similar_list:
        kb = get_new_search_button()
        return await call.message.edit_text(
            "Похожие селебы недоступны. Начните новый поиск.",
            reply_markup=kb.as_markup()
        )

    payload = call.data

    def build_list_kb():
        kb = InlineKeyboardBuilder()
        for rec in similar_list:
            kb.button(text=rec["name"].title(), callback_data=f"similar:select:{rec['id']}")
        kb.button(text="⬅️ Назад к карточке", callback_data="similar:back")
        kb.button(text="🔄 Новый поиск", callback_data="new_search")
        kb.button(text="📝 Отправить заявку модератору", callback_data="similar:request")
        kb.adjust(1)
        return kb.as_markup()

    async def render_card(chosen: dict):
        text = build_card_text(chosen)

        status = (chosen.get("status") or "").lower()
        cat_l = (chosen.get("category") or "").strip().lower()
        geo_l = (chosen.get("geo") or "").strip().lower()
        show_celebs = False
        if status == "нельзя использовать":
            text += "\n\nВы можете ознакомиться с доступным списком селеб по данному гео/категории:"
            show_celebs = True
            await state.update_data(geo=geo_l, cat=cat_l)

        user_id = call.from_user.id
        kb = get_new_search_button(show_celebs=show_celebs, show_edit_button=True,is_moderator=is_moderator(user_id))
        kb.button(text="⬅️ Назад к списку", callback_data="similar:open")
        kb.adjust(1)
        return await call.message.edit_text(text, reply_markup=kb.as_markup())

    if payload == "similar:open":
        return await call.message.edit_text(
            "Нашли похожих — выберите нужную.\n"
            "Если нужной Селебы нет, нажмите «📝 Отправить заявку модератору».",
            reply_markup=build_list_kb()
        )

    elif payload == "similar:back":
        chosen = next((r for r in similar_list if int(r["id"]) == int(initial_celeb_id)), None) if initial_celeb_id is not None else None
        if chosen is None:
            chosen = similar_list[0]
        return await render_card(chosen)

    elif payload.startswith("similar:select:"):
        try:
            sel_id = int(payload.split(":", 2)[2])
        except ValueError:
            return await call.message.edit_text("Не удалось определить селебу. Выберите из списка:", reply_markup=build_list_kb())

        chosen = next((r for r in similar_list if int(r["id"]) == sel_id), None)
        if not chosen:
            return await call.message.edit_text("Не нашли выбранную запись. Выберите из списка:", reply_markup=build_list_kb())

        return await render_card(chosen)

    elif payload == "similar:request":
        query_name = data.get("query_name")
        category = data.get("cat")
        geo = data.get("geo")
        if not (query_name and category and geo):
            return await call.message.edit_text(
                "Не хватает данных для заявки. Начните новый поиск и укажите имя/категорию/гео.",
                reply_markup=get_new_search_button().as_markup()
            )

        prompt_id = data.get("prompt_message_id") or call.message.message_id
        username = call.from_user.username
        request_id = await send_request_to_moderator(
            query_name, category, geo, prompt_id, username, call.message, requests_service, subscribers_service
        )

        text = f"Ваш запрос в обработке, ожидайте ответа модератора. Номер заявки: {request_id}"
        return await call.message.edit_text(text, reply_markup=get_new_search_button().as_markup())

    return await call.message.edit_text("Выберите нужную Селебу из списка:", reply_markup=build_list_kb())





