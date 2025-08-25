from aiogram.utils.keyboard import InlineKeyboardBuilder

from synonyms import geo_flags, category_synonyms


def get_new_search_button(show_edit_button: bool = False, is_moderator: bool = False, show_celebs: bool = False, similar=False):
    kb = InlineKeyboardBuilder()
    if show_celebs:
        kb.button(text="Посмотреть селеб", callback_data="available_celebs")
    kb.button(text="🔄 Новый поиск", callback_data="new_search")
    if show_edit_button and is_moderator:
        kb.button(text="✏️ Редактировать", callback_data="edit")
    if similar:
        kb.button(text="❓ Не та Cелеба?", callback_data="similar:open")
    return kb


def get_geo_keyboard(back_button_callback_data:str = "back:method", action_type:str = "geo", back_button_text:str = "🔙 Назад"):
    kb = InlineKeyboardBuilder()
    for key, label in geo_flags.items():
        kb.button(text=label, callback_data=f"{action_type}:{key}")
    kb.button(text=back_button_text, callback_data=back_button_callback_data)
    kb.adjust(3)
    return kb


def get_categories_keyboard(back_button_callback_data:str, action_type:str = "cat", back_button_text:str = "🔙 Назад"):
    categories = sorted(set(category_synonyms.values()))
    kb = InlineKeyboardBuilder()
    for cat in categories:
        if cat.strip().lower() == "жкт":
            label = "ЖКТ"
        else:
            label = " ".join(word.capitalize() for word in cat.split())
        kb.button(text=label, callback_data=f"{action_type}:{cat}")
    kb.button(text=back_button_text, callback_data=back_button_callback_data)
    kb.adjust(2)
    return kb


def get_edit_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Селеба", callback_data="edit_field:name")
    kb.button(text="Статус", callback_data="edit_field:status")
    kb.button(text="Категория", callback_data="edit_field:cat")
    kb.button(text="Гео", callback_data="edit_field:geo")
    kb.button(text="❌Удалить", callback_data="edit_field:delete")
    kb.button(text="✅Готово", callback_data="edit_field:back")
    kb.adjust(2)
    return kb


def cancel_role_change_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌Отмена", callback_data="cancel_role_change")
    return kb