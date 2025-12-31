import logging
import re

from aiogram.types import Message
from stp_database.models.STP import Employee

from tgbot.config import load_config
from tgbot.misc.dicts import roles

logger = logging.getLogger(__name__)

config = load_config(".env")


async def check_premium_emoji(message: Message) -> tuple[bool, list[str]]:
    emoji_ids = []
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                emoji_ids.append(entity.custom_emoji_id)
    return len(emoji_ids) > 0, emoji_ids


def extract_clever_link(message_text):
    pattern = r"https?://[^\s]*clever\.ertelecom\.ru/content/space/[^\s]*"

    match = re.search(pattern, message_text)
    if match:
        return match.group(0)
    return None


async def get_target_forum(user: Employee):
    if user.division == "НЦК":
        if user.is_trainee:
            return config.forum.nck_trainee_forum_id
        else:
            return config.forum.nck_main_forum_id
    else:
        if user.is_trainee:
            return config.forum.ntp_trainee_forum_id
        else:
            return config.forum.ntp_main_forum_id


def get_role(role_id: int = None, role_name: str = None, return_id: bool = False):
    """Получает информацию о роли.

    Args:
        role_id: Идентификатор роли
        role_name: Название роли
        return_id: Нужно ли возвращать идентификатор

    Returns:
        Название и эмодзи роли или идентификатор роли
    """
    if role_id is not None:
        return role_id if return_id else roles.get(role_id)

    if role_name is not None:
        for r_id, data in roles.items():
            if data["name"] == role_name:
                return r_id if return_id else data

    return None


def get_gender_emoji(name: str) -> str:
    """Определяет пол по имени.

    Args:
        name: Полные ФИО

    Returns:
        Эмодзи гендера
    """
    parts = name.split()
    if len(parts) >= 3:
        patronymic = parts[2]
        if patronymic.endswith("на"):
            return "👩‍💼"
        elif patronymic.endswith(("ич", "ович", "евич")):
            return "👨‍💼"
    return "👨‍💼"


def short_name(full_name: str) -> str:
    """Достает фамилию и имя из ФИО.

    Args:
        full_name: Полные ФИО

    Returns:
        Фамилия и имя
    """
    clean_name = full_name.split("(")[0].strip()
    parts = clean_name.split()

    if len(parts) >= 2:
        return " ".join(parts[:2])
    return clean_name


def format_fullname(
    user: Employee,
    short: bool = True,
    gender_emoji: bool = False,
) -> str:
    """Форматирует ФИО пользователя.

    Args:
        user: Экземпляр пользователя с моделью Employee
        short: Нужно ли сократить до ФИ
        gender_emoji: Нужно ли добавлять эмодзи гендеры к ФИО

    Returns:
        Форматированная строка с указанными параметрами
    """
    user_fullname = user.fullname
    user_username = user.username
    user_user_id = user.user_id

    # Форматируем ФИО
    if short and user_fullname:
        formatted_fullname = short_name(user_fullname)
    else:
        formatted_fullname = user_fullname

    # Добавляем ссылку, если есть username или user_id
    if user_username is not None:
        formatted_fullname = f"<a href='t.me/{user_username}'>{formatted_fullname}</a>"
    elif user_username is None and user_user_id is not None:
        formatted_fullname = (
            f"<a href='tg://user?id={user_user_id}'>{formatted_fullname}</a>"
        )

    # Добавляем эмодзи гендера, если требуется
    if gender_emoji and user_fullname:
        emoji = get_gender_emoji(user_fullname)
        formatted_fullname = f"{emoji} {formatted_fullname}"

    return formatted_fullname
