import re

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asyncpg import UniqueViolationError

from config import logger, ADMIN_ID
from db.celebrity_service import CelebrityService
from db.requests_service import RequestsService
from db.subcribers_service import SubscribersService
from keyboards import get_new_search_button, get_edit_keyboard, get_categories_keyboard, get_geo_keyboard, \
    cancel_role_change_kb
from models import USER_ROLES
from states import EditCelebrity, EditUserRole
from synonyms import geo_synonyms
from utils import is_moderator, replace_param_in_text, parse_celebrity_from_msg, set_subscriber_username


PENDING_MESSAGES = {}


async def edit_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id

    if not is_moderator(user_id):
        await call.answer("Недостаточно прав для редактирования", show_alert=True)
        return

    orig_message_id = call.message.message_id
    orig_message_text = call.message.text
    celeb_params = parse_celebrity_from_msg(orig_message_text)

    await state.update_data(
        orig_message_id=orig_message_id,
        orig_message_text=orig_message_text,
        celebrity={
            "name": celeb_params.get("селеба"),
            "category": celeb_params.get("категория"),
            "geo": celeb_params.get("гео"),
            "status": celeb_params.get("статус"),
        }
    )

    await call.message.edit_reply_markup(reply_markup=None)
    await show_edit_menu(call.bot, call.message.chat.id, state)
    await call.answer()


async def field_chosen(call: CallbackQuery, state: FSMContext):
    await call.answer()
    field = call.data.split(":")[1]
    user_id = int(call.from_user.id)

    if field == "back":
        data = await state.get_data()
        orig_message_id = data.get("orig_message_id")
        await call.message.delete()
        await state.clear()

        new_search_b = get_new_search_button(show_edit_button=True, is_moderator=is_moderator(user_id))
        await call.bot.edit_message_reply_markup(
            message_id=orig_message_id,
            chat_id=call.message.chat.id,
            reply_markup=new_search_b.as_markup())

    if field == "name":
        await state.set_state(EditCelebrity.editing_name)
        back_kb = InlineKeyboardBuilder()
        back_kb.button(text="🔙 Назад", callback_data="edit:back")
        back_kb.adjust(1)
        await call.message.edit_text("Напишите новое имя:", reply_markup=back_kb.as_markup())

    if field == "cat":
        await state.set_state(EditCelebrity.editing_param)
        cat_kb = get_categories_keyboard(back_button_callback_data="edit:back", action_type="edit_cat")
        await call.message.edit_text("Выберите категорию:", reply_markup=cat_kb.as_markup())

    if field == "geo":
        await state.set_state(EditCelebrity.editing_param)
        geo_kb = get_geo_keyboard(back_button_callback_data="edit:back", action_type="edit_geo")
        await call.message.edit_text("Выберите гео:", reply_markup=geo_kb.as_markup())

    if field == "status":
        await state.set_state(EditCelebrity.editing_param)
        status_kb = InlineKeyboardBuilder()
        status_kb.button(text="Согласована✅", callback_data="edit_status:approved")
        status_kb.button(text="Нельзя Использовать ⛔", callback_data="edit_status:forbidden")
        status_kb.button(text="🔙 Назад", callback_data="edit:back")
        status_kb.adjust(2)
        await call.message.edit_text("Выберите статус:", reply_markup=status_kb.as_markup())

    if field == "delete":
        await state.set_state(EditCelebrity.deleting_entry)
        confirm_kb = InlineKeyboardBuilder()
        confirm_kb.button(text="Да, удалить!", callback_data="edit:delete")
        confirm_kb.button(text="Отмена", callback_data="edit:back")
        confirm_kb.adjust(2)
        await call.message.edit_text("Точно удаляем эту Селебу?", reply_markup=confirm_kb.as_markup())

    await state.update_data(editing_param_msg_id=call.message.message_id)


async def name_edited(message: Message, state: FSMContext, celebrity_service: CelebrityService):
    data = await state.get_data()
    name_input = message.text.strip()
    celeb_data = data.get("celebrity")
    orig_message_id = data.get("orig_message_id")
    orig_message_text = data.get("orig_message_text")
    editing_param_msg_id = data.get("editing_param_msg_id")

    orig_msg_new_text = replace_param_in_text(text=orig_message_text, new_name=name_input)
    await message.bot.delete_message(message_id=editing_param_msg_id, chat_id=message.chat.id)
    await message.bot.edit_message_text(text=orig_msg_new_text, chat_id=message.chat.id, message_id=orig_message_id)

    try:
        await celebrity_service.update_celebrity(**celeb_data, new_name=name_input.lower())
        celeb_data["name"] = name_input.lower()
        await state.update_data(celebrity=celeb_data, orig_message_text=orig_msg_new_text)
    except UniqueViolationError as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)

    await message.delete()
    await show_edit_menu(message.bot, message.chat.id, state)


async def new_param_chosen(call: CallbackQuery, state: FSMContext, celebrity_service: CelebrityService):
    await call.answer()

    prefix, new_value = call.data.split(":", 1)
    new_value = re.sub(r'[^\w\s]', '', new_value, flags=re.UNICODE)
    new_value = new_value.strip().lower()

    data = await state.get_data()
    orig_message_text = data.get("orig_message_text")
    editing_param_msg_id = data.get("editing_param_msg_id")
    orig_message_id = data.get("orig_message_id")

    celeb_data = data.get("celebrity")

    param_map = {"edit_cat": "new_cat", "edit_geo": "new_geo", "edit_status": "new_status"}
    param_to_use = param_map.get(prefix)
    if param_to_use == "new_geo":
        new_value = geo_synonyms.get(new_value).capitalize()
    if param_to_use == "new_status":
        new_value = "согласована" if new_value == "approved" else "нельзя использовать"

    orig_msg_new_text = replace_param_in_text(text=orig_message_text, **{param_to_use: new_value})
    try:
        await call.bot.edit_message_text(text=orig_msg_new_text, chat_id=call.message.chat.id, message_id=orig_message_id)
    except TelegramBadRequest:
        pass

    try:
        await celebrity_service.update_celebrity(**celeb_data, **{param_to_use: new_value})
        if param_to_use == "new_geo":
            celeb_data["geo"] = new_value
        if param_to_use == "new_status":
            celeb_data["status"] = new_value
        if param_to_use == "new_cat":
            celeb_data["category"] = new_value
        await state.update_data(celebrity=celeb_data, orig_message_text=orig_msg_new_text)

        await state.update_data(celebrity=celeb_data,orig_message_text=orig_msg_new_text)
    except UniqueViolationError as e:
        logger.error(e)

    await call.bot.delete_message(message_id=editing_param_msg_id, chat_id=call.message.chat.id)
    await show_edit_menu(call.message.bot, call.message.chat.id, state)


async def delete_celebrity_handler(call: CallbackQuery, state: FSMContext, celebrity_service: CelebrityService):
    await call.answer()
    data = await state.get_data()
    celeb_data = data.get("celebrity")
    orig_message_id = data.get("orig_message_id")
    status = celeb_data.get("status")
    status = re.sub(r'[^\w\s]', '', status, flags=re.UNICODE)
    celeb_data["status"] = status

    chat_id = call.message.chat.id
    try:
        await celebrity_service.delete_celebrity(**celeb_data)
    except Exception as e:
        await call.message.answer("Ошибка при удалении записи")
        logger.error("Error deleting celebrity: ", e)
    else:
        new_search_b = get_new_search_button()
        await call.message.answer("Запись удалена", reply_markup=new_search_b.as_markup())
        await call.message.delete()
        await call.bot.delete_message(message_id=orig_message_id, chat_id=chat_id)
        await state.clear()


async def show_edit_menu(bot, chat_id, state):
    edit_kb = get_edit_keyboard()
    await state.set_state(EditCelebrity.choosing_field)
    await bot.send_message(chat_id, "Что редактируем?", reply_markup=edit_kb.as_markup())


async def edit_back_button_handler(call: CallbackQuery, state: FSMContext):
    if call.data == "edit:back":
        await call.answer()
        await call.message.delete()
        await show_edit_menu(call.bot, call.message.chat.id, state)
        return


async def cmd_requests(message: Message, requests_service: RequestsService):
    await message.delete()
    requests = await requests_service.get_all_pending_requests()
    if not requests:
        await message.answer("Активных заявок нет.")
        return

    for request in requests:
        request_id, name, cat, geo, username = request[:5]
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Одобрить", callback_data=f"approve:{request_id}")
        builder.button(text="⛔ Забанить", callback_data=f"ban:{request_id}")
        builder.button(text="🗑 Удалить заявку", callback_data=f"delete:{request_id}")
        builder.adjust(2, 1)

        await message.answer(
            f"<b>Необработанная заявка:</b>\nИмя: {name.title()}\nКатегория: {cat.title()}\nГео: {geo.title()}\nНомер Заявки: {request_id}\nЮзер: {'@'+username if username else ''}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )


async def delete_request_handler(call: CallbackQuery, requests_service: RequestsService):
    await call.message.delete()
    request_id = call.data.split(":", 1)[1]
    await requests_service.pop_pending_request(int(request_id))
    await call.answer(text="Заявка удалена")


async def send_request_to_moderator(name_input: str, category: str, geo: str, prompt_id: int, username:str, message: Message, requests_service: RequestsService, subscribers_service: SubscribersService):
    moderators = await subscribers_service.get_moderators()
    observers = await subscribers_service.get_observers()
    moderators.append(ADMIN_ID)
    msg_ids = []

    request_id = await requests_service.add_pending_request(
        message.from_user.id, message.chat.id, message.message_id,
        name_input, category, geo, prompt_id, username
    )

    text = (
        f"<b>Новая заявка:</b>\n\n"
        f"Имя: {name_input.title()}\n"
        f"Категория: {category.title()}\n"
        f"Гео: {geo.title()}\n"
        f"Номер Заявки: {request_id}\n"
        f"Юзер: @{username}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve:{request_id}")
    builder.button(text="⛔ Забанить", callback_data=f"ban:{request_id}")
    builder.adjust(2)

    for mod_id in moderators:
        try:
            msg = await message.bot.send_message(
                chat_id=mod_id,
                text=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            msg_ids.append({"chat_id": mod_id, "message_id": msg.message_id})

        except Exception as e:
            logger.warning("Failed to send message to moderator", exc_info=e)

    for ob_id in observers:
        try:
            msg = await message.bot.send_message(
                chat_id=ob_id,
                text=text,
                parse_mode="HTML"
            )
            msg_ids.append({"chat_id": ob_id, "message_id": msg.message_id})

        except Exception as e:
            logger.warning("Failed to send message to observer", exc_info=e)

    PENDING_MESSAGES[request_id] = msg_ids

    return request_id


async def handle_request_moderator(call, requests_service: RequestsService, celebrity_service: CelebrityService):
    action, req_id = call.data.split(":", 1)
    is_approve = (action == "approve")

    pending = await requests_service.pop_pending_request(int(req_id))
    if not pending:
        await call.answer("Заявка не найдена или уже обработана", show_alert=True)
        await call.message.delete()
        return

    chat_id = pending.get("chat_id")
    message_id = pending.get("message_id")
    name     = pending.get("celebrity_name")
    category = pending.get("category")
    geo      = pending.get("geo")
    prompt_id = pending.get("bot_message_id")
    username = pending.get("username")
    status = "Согласована" if is_approve else "Нельзя Использовать"

    name, category, geo, status = map(lambda x: x.lower() if x else '', (name, category, geo, status))
    handled = await celebrity_service.insert_celebrity(name, category, geo, status)
    handled.update({"chat_id": chat_id, "message_id": message_id, "prompt_id": prompt_id})

    message_ids = PENDING_MESSAGES.get(int(req_id), [])
    for msg_info in message_ids:
        try:
            await call.bot.edit_message_text(
                chat_id=msg_info["chat_id"],
                message_id=msg_info["message_id"],
                text=f"<b>Заявка обработана:</b>\n\n"
                     f"Имя: {name.title()}\n"
                     f"Категория: {category.title()}\n"
                     f"Гео: {geo.title()}\n"
                     f"Статус: {status.title()}\n"
                     f"Номер Заявки: {req_id}\nЮзер: @{username}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to edit request message {msg_info}", exc_info=e)

    if int(req_id) in PENDING_MESSAGES:
        del PENDING_MESSAGES[int(req_id)]

    return handled


async def cmd_users(message: Message, subscribers_service: SubscribersService, bot: Bot):
    await message.delete()
    users = await subscribers_service.get_all_subscribers()
    updated_users = []
    for user in users:
        username = user.get("username")
        chat_id = user.get("chat_id")
        if not username:
            try:
                username = await set_subscriber_username(chat_id, bot, subscribers_service)
            except Exception:
                username = None
        updated_users.append(f"@{username} ID: {chat_id}" if username else f"ID: {chat_id}")

    if not updated_users:
        await message.answer("Юзеры недоступны")
    else:
        await message.answer("\n".join(updated_users))


async def cmd_role(message: Message, state: FSMContext):
    await state.clear()
    await message.delete()
    await state.set_state(EditUserRole.waiting_for_id)
    kb = cancel_role_change_kb()
    msg = await message.answer("Введите ID пользователя, которому хотите поменять роль:", reply_markup=kb.as_markup())
    await state.update_data(bot_message_id=msg.message_id)


async def cancel_role_handler(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.clear()
    await call.answer()


async def cmd_role_receive_user_id(message: Message, state: FSMContext, subscribers_service: SubscribersService, bot: Bot):
    data = await state.get_data()
    bot_msg_id = data["bot_message_id"]
    chat_id = message.chat.id

    try:
        await message.bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
    except TelegramBadRequest:
        pass

    user_id_str = message.text.strip()

    if not user_id_str.isdigit():
        kb = cancel_role_change_kb()
        await message.answer("ID должен быть числом, попробуйте еще раз.")
        await message.answer("Введите ID пользователя, которому хотите поменять роль:", reply_markup=kb.as_markup())
        await state.set_state(EditUserRole.waiting_for_id)
        await message.delete()
        return

    user_id = int(user_id_str)
    user = await subscribers_service.get_user(user_id)
    await state.update_data(user_id=user_id)

    if not user:
        kb = InlineKeyboardBuilder()
        kb.button(text="Да", callback_data="resume_role_changing")
        kb.button(text="❌Отмена", callback_data="cancel_role_change")
        await message.answer(
            f"Пользователь с ID {user_id} не найден в базе.\n"
            "Вы хотите продолжить и назначить роль на этот ID?",
            reply_markup=kb.as_markup()
        )
        await message.delete()
        return

    username = user.get("username")
    if not username:
        try:
            username = await set_subscriber_username(user_id, bot, subscribers_service)
        except Exception:
            username = None

    await message.answer("Пользователь найден:\n"
                         f"ID: {user.get('chat_id')}\n"
                         f"username: {username}\n"
                         f"Role: {user.get('role').capitalize()}\n")
    await send_role_selection(state, chat_id, message.bot, user_id)
    await message.delete()


async def send_role_selection(state: FSMContext, chat_id: int, bot: Bot, user_id: int):
    await state.set_state(EditUserRole.waiting_for_role_choice)
    kb = InlineKeyboardBuilder()

    for role in USER_ROLES:
        if role.lower() == "admin":
            continue
        kb.button(text=role.capitalize(), callback_data=f"role_set:{user_id}:{role}")

    kb.button(text="❌Отмена", callback_data="cancel_role_change")
    kb.adjust(2)

    await bot.send_message(chat_id=chat_id, text="Выберите новую роль:", reply_markup=kb.as_markup())


async def resume_role_changing_handler(call: CallbackQuery, state: FSMContext, subscribers_service: SubscribersService):
    await call.answer()
    await call.message.delete()
    data = await state.get_data()
    user_id = data["user_id"]

    if not user_id:
        await call.answer("Что-то пошло не так. Пожалуйста, повторите ввод ID.")
        await state.clear()

        kb = cancel_role_change_kb()
        await call.message.answer("Введите ID пользователя, которому хотите поменять роль:", reply_markup=kb.as_markup())
        await state.set_state(EditUserRole.waiting_for_id)
        return

    user = await subscribers_service.add_subscriber(user_id)
    if not user:
        await call.message.answer("Что-то пошло не так. Ошибка добавления пользователя")
        await state.clear()
        return

    await call.message.answer("Пользователь добавлен в БД")
    await send_role_selection(state, call.message.chat.id, call.bot, user_id)


async def role_chosen_handler(call: CallbackQuery, state: FSMContext, subscribers_service: SubscribersService):
    await call.answer()
    _, user_id_str, new_role = call.data.split(":")

    user_id = int(user_id_str)

    success = await subscribers_service.update_role(user_id, new_role)
    if not success:
        await call.message.answer("Ошибка обновления роли")
        await state.clear()
        return

    await call.message.answer(f"Роль пользователя {user_id} успешно изменена на {new_role.capitalize()}")
    await state.clear()
    await call.message.delete()
