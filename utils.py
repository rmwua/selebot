import re

from aiogram import Bot
from transliterate import translit
import unidecode

import config
from db.subscribers_service import SubscribersService


def is_moderator(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


def replace_param_in_text(text: str, new_name:str=None, new_geo:str=None, new_status:str=None, new_cat:str=None) -> str:
    params = {
        "селеба": new_name,
        "гео": new_geo,
        "статус": new_status,
        "категория": new_cat,
    }
    lines = text.splitlines()
    new_lines = []

    for line in lines:
        key = line.split(":", 1)[0].strip().lower()
        if key in params and params[key] is not None:
            new_lines.append(f"{key.capitalize()}: {params[key].capitalize()}")
        else:
            new_lines.append(line)
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

