import re

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asyncpg import UniqueViolationError
import db
from config import logger
from keyboards import get_new_search_button, get_edit_keyboard, get_categories_keyboard, get_geo_keyboard
from states import EditCelebrity
from synonyms import geo_synonyms
from utils import is_moderator, replace_param_in_text, parse_celebrity_from_msg


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
    field = call.data.split(":")[1]
    user_id = int(call.from_user.id)

    if field == "back":
        data = await state.get_data()
        orig_message_id = data.get("orig_message_id")
        delete_ids = data.get("delete_message_ids", [])
        if delete_ids:
            await call.bot.delete_messages(chat_id=call.message.chat.id, message_ids=delete_ids)
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
        status_kb.button(text="✅ Согласована", callback_data="edit_status:approved")
        status_kb.button(text="⛔ Нельзя Использовать", callback_data="edit_status:forbidden")
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


async def name_edited(message: Message, state: FSMContext):
    data = await state.get_data()
    name_input = message.text.strip()
    celeb_data = data.get("celebrity")
    orig_message_id = data.get("orig_message_id")
    orig_message_text = data.get("orig_message_text")
    editing_param_msg_id = data.get("editing_param_msg_id")
    delete_ids = data.get("delete_message_ids", [])

    orig_msg_new_text = replace_param_in_text(text=orig_message_text, new_name=name_input)
    await message.bot.delete_message(message_id=editing_param_msg_id, chat_id=message.chat.id)
    await message.bot.edit_message_text(text=orig_msg_new_text, chat_id=message.chat.id, message_id=orig_message_id)

    try:
        await db.update_celebrity(**celeb_data, new_name=name_input.lower())
    except UniqueViolationError as e:
        bot_msg = await message.answer(f"Ошибка изменения имени, селеба с такими же параметрами(имя, гео, категория) уже есть в базе")
    except Exception as e:
        bot_msg = await message.answer(f"Ошибка изменения имени")
    else:
        bot_msg = await message.answer(f"Имя изменено на {name_input}")

    delete_ids.append(bot_msg.message_id)
    await state.update_data(delete_message_ids=delete_ids)
    await message.delete()
    await show_edit_menu(message.bot, message.chat.id, state)


async def new_param_chosen(call: CallbackQuery, state: FSMContext):
    await call.answer()

    prefix, new_value = call.data.split(":", 1)
    new_value = re.sub(r'[^\w\s]', '', new_value, flags=re.UNICODE)
    new_value = new_value.strip().lower()

    data = await state.get_data()
    orig_message_text = data.get("orig_message_text")
    editing_param_msg_id = data.get("editing_param_msg_id")
    orig_message_id = data.get("orig_message_id")

    celeb_data = data.get("celebrity")
    delete_ids = data.get("delete_message_ids", [])

    param_map = {"edit_cat": "new_cat", "edit_geo": "new_geo", "edit_status": "new_status"}
    param_to_use = param_map.get(prefix)
    if param_to_use == "new_geo":
        new_value = geo_synonyms.get(new_value).capitalize()
    if param_to_use == "new_status":
        new_value = "согласована" if new_value == "approved" else "нельзя использовать"

    orig_msg_new_text = replace_param_in_text(text=orig_message_text, **{param_to_use: new_value})
    await call.bot.edit_message_text(text=orig_msg_new_text, chat_id=call.message.chat.id, message_id=orig_message_id)

    try:
        await db.update_celebrity(**celeb_data, **{param_to_use: new_value})
    except UniqueViolationError as e:
        bot_msg = await call.message.answer(
            f"Ошибка изменения категории, селеба с такими же параметрами(имя, гео, категория) уже есть в базе")
    except Exception as e:
        bot_msg = await call.message.answer(f"Ошибка изменения")
    else:
        bot_msg = await call.message.answer(f"Параметр успешно изменен на {new_value}")

    delete_ids.append(bot_msg.message_id)
    await state.update_data(delete_message_ids=delete_ids)
    await call.bot.delete_message(message_id=editing_param_msg_id, chat_id=call.message.chat.id)
    await show_edit_menu(call.message.bot, call.message.chat.id, state)


async def delete_celebrity_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    celeb_data = data.get("celebrity")
    orig_message_id = data.get("orig_message_id")
    status = celeb_data.get("status")
    status = re.sub(r'[^\w\s]', '', status, flags=re.UNICODE)
    celeb_data["status"] = status

    chat_id = call.message.chat.id
    try:
        await db.delete_celebrity(**celeb_data)
    except Exception as e:
        await call.message.answer("Ошибка при удалении записи")
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