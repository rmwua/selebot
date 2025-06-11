from aiogram.utils.keyboard import InlineKeyboardBuilder

from synonyms import geo_flags, category_synonyms


def new_search_button():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Новый поиск", callback_data="new_search")

    return kb


def geo_keyboard():
    kb = InlineKeyboardBuilder()
    for key, label in geo_flags.items():
        kb.button(text=label, callback_data=f"geo:{key}")
    kb.button(text="🔙 Назад", callback_data="back:method")
    kb.adjust(3)
    return kb


def categories_keyboard():
    categories = sorted(set(category_synonyms.values()))
    kb = InlineKeyboardBuilder()
    for cat in categories:
        if cat.strip().lower() == "жкт":
            label = "ЖКТ"
        else:
            label = " ".join(word.capitalize() for word in cat.split())
        kb.button(text=label, callback_data=f"cat:{cat}")
    kb.button(text="🔙 Назад", callback_data="back:geo")
    kb.adjust(2)

    return kb
