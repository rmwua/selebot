import re

from transliterate import translit
import unidecode

import config


def is_moderator(user_id: int) -> bool:
    return user_id == config.MODERATOR_ID


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


