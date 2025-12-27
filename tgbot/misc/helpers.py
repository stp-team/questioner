import logging
import re

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from stp_database.models.STP import Employee

from tgbot.config import load_config

logger = logging.getLogger(__name__)

config = load_config(".env")


async def disable_previous_buttons(message: Message, state: FSMContext):
    """Функция для отключения inline кнопок в сообщениях"""
    state_data = await state.get_data()
    messages_with_buttons = state_data.get("messages_with_buttons", [])

    for msg_id in messages_with_buttons:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id, message_id=msg_id, reply_markup=None
            )
        except Exception as e:
            # Handle case where message might be deleted or not editable
            print(f"Could not disable buttons for message {msg_id}: {e}")

    # Clear the list after disabling buttons
    await state.update_data(messages_with_buttons=[])


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
    user: Employee = None,
    short: bool = True,
    gender_emoji: bool = False,
    fullname: str = None,
    username: str = None,
    user_id: int = None,
) -> str:
    """Форматирует ФИО пользователя.

    Args:
        user: Экземпляр пользователя с моделью Employee
        short: Нужно ли сократить до ФИ
        gender_emoji: Нужно ли добавлять эмодзи гендеры к ФИО
        fullname: ФИО пользователя (используется когда user=None)
        username: Username пользователя (используется когда user=None)
        user_id: ID пользователя (используется когда user=None)

    Returns:
        Форматированная строка с указанными параметрами
    """
    # Определяем источник данных
    if user is not None:
        # Используем данные из объекта Employee
        user_fullname = user.fullname
        user_username = user.username
        user_user_id = user.user_id
    else:
        # Используем переданные параметры
        user_fullname = fullname or ""
        user_username = username
        user_user_id = user_id

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
