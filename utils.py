import re

from aiogram import Bot
from transliterate import translit
import unidecode

import config
from db.subscribers_service import SubscribersService


async def is_moderator(user_id: int, subscribers_service: SubscribersService) -> bool:
    if user_id == config.ADMIN_ID:
        return True
    role = await subscribers_service.get_user_role(user_id)
    return (role or "").lower() == "admin"


def replace_param_in_text(text: str, new_name:str=None, new_geo:str=None, new_status:str=None, new_cat:str=None, new_reason: str=None) -> str:
    params = {
        "селеба": new_name,
        "гео": new_geo,
        "статус": new_status,
        "категория": new_cat,
        "причина": new_reason,
    }

    lines = text.splitlines()
    keys_present = set()
    new_lines = []

    for line in lines:
        key = line.split(":", 1)[0].strip().lower()
        keys_present.add(key)

        if key in params and params[key] is not None:
            new_lines.append(f"{key.capitalize()}: {params[key].capitalize()}")
        else:
            new_lines.append(line)

    for key, value in params.items():
        if value is not None and key not in keys_present:
            new_lines.append(f"{key.capitalize()}: {value.capitalize()}")

    return "\n".join(new_lines)


def parse_celebrity_from_msg(msg:str) -> dict:
    result = {}
    for line in msg.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip().lower()] = value.strip().lower()
    return result


def sanitize_cyr(text: str) -> str:
    import re
    if re.search(r'[a-z]', text, re.I):
        try:
            text = translit(text, 'ru')
        except Exception:
            pass

    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return text.strip().lower()


def sanitize_ascii(text: str) -> str:
    if re.fullmatch(r'[A-Za-z0-9\s]+', text):
        return text.strip().lower()
    # для ascii_name: транслитерируем, потом очищаем
    return re.sub(r"[^\w\s]", "", unidecode.unidecode(text), flags=re.UNICODE).strip().lower()


async def set_subscriber_username(chat_id: int , bot: Bot, subscribers_service: SubscribersService) -> str | None:
    tg_user = await bot.get_chat(chat_id)
    username = tg_user.username
    if username:
        await subscribers_service.add_subscriber(chat_id, username)
    return username


async def is_admin_or_moderator_or_observer(user_id: int, subscribers_service) -> bool:
    if user_id == config.ADMIN_ID:
        return True
    moderators = await subscribers_service.get_moderators()
    observers = await subscribers_service.get_observers()
    return user_id in moderators or user_id in observers


def split_names(raw: str) -> list[str]:
    parts = re.split(r'[,;\n]+', raw, flags=re.UNICODE)
    return [p.strip().lower() for p in parts if p.strip()]


def build_card_text(celeb: dict) -> str:
    name = celeb["name"]
    status = celeb["status"]
    geo = celeb["geo"]
    raw_cat = celeb["category"]
    category = raw_cat.strip().lower()
    reason = celeb.get("reason") or None

    display_category = "ЖКТ" if category == "жкт" else category.title()
    emoji = "✅" if status.lower() == "согласована" else "⛔"
    lines = [
        f"Селеба: {name.title()}",
    ]

    lines.append(f"Статус: {status.title()}{emoji}"),
    if status.lower() == 'нельзя использовать' and reason:
        lines.append(f"Причина: {reason}")
    lines.append(f"Категория: {display_category}")
    lines.append(f"Гео: {geo.title()}")

    return "\n".join(lines)
