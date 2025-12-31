import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

from tgbot.config import load_config

config = load_config(".env")

logger = logging.getLogger(__name__)


def _is_group(message: Message) -> bool:
    """Проверяет, является ли чат группой или супергруппой."""
    return message.chat.type in ["group", "supergroup"]


def _is_topic(message: Message) -> bool | None:
    """Проверяет, является ли сообщение сообщением топика."""
    return (
        message.is_topic_message
        and message.message_thread_id is not None
        and message.message_thread_id != 1
    )


def _is_bot(message: Message) -> bool:
    """Проверяет, является ли сообщение сообщением от бота."""
    return (
        message.bot is not None
        and message.from_user is not None
        and message.from_user.id == message.bot.id
    )


def _has_valid_command(message: Message, command: str | None) -> bool:
    """Проверяет, содержит ли сообщение требуемую команду."""
    if not command:
        return True
    return message.text is not None and message.text.startswith(f"/{command}")


def _is_service_message(message: Message) -> bool:
    """Проверяет, является ли сообщение сервисным."""
    return message.from_user is None


def _is_valid_user_message(message: Message) -> bool:
    """Проверяет базовые требования для пользовательского сообщения."""
    return not _is_service_message(message) and not _is_bot(message)


def _is_main_topic(message: Message) -> bool:
    """Проверяет, находится ли сообщение в главном топике форума."""
    chat_id_str = str(message.chat.id)
    main_forum_ids = [
        config.forum.ntp_main_forum_id,
        config.forum.ntp_trainee_forum_id,
        config.forum.nck_main_forum_id,
        config.forum.nck_trainee_forum_id,
    ]
    return chat_id_str in main_forum_ids and message.message_thread_id is None


class IsTopicMessage(BaseFilter):
    """Фильтр для обработки сообщений дежурных в топиках."""

    async def __call__(self, message: Message, **_) -> bool:
        # Проверка на группу/супергруппу и тему
        if not _is_group(message) or not _is_topic(message):
            return False

        # Проверка на валидное пользовательское сообщение (исключаем ботов)
        if _is_bot(message):
            return False

        return True


class IsTopicMessageWithCommand(BaseFilter):
    """Фильтр для обработки сообщений с командами в топиках."""

    def __init__(self, command: str | None = None):
        self.command = command

    async def __call__(self, message: Message, **_) -> bool:
        # Проверка команды
        if not _has_valid_command(message, self.command):
            return False

        # Проверка на группу/супергруппу и тему
        if not _is_group(message) or not _is_topic(message):
            return False

        # Проверка на валидное пользовательское сообщение
        if not _is_valid_user_message(message):
            return False

        return True


class IsMainTopicMessageWithCommand(BaseFilter):
    """Фильтр для обработки сообщений с командами в главных топиках форумов."""

    def __init__(self, command: str | None = None):
        self.command = command

    async def __call__(self, message: Message, **_) -> bool:
        # Проверка команды
        if not _has_valid_command(message, self.command):
            return False

        # Проверка на группу/супергруппу и главный топик
        if not _is_group(message) or not _is_main_topic(message):
            return False

        # Проверка на валидное пользовательское сообщение
        if not _is_valid_user_message(message):
            return False

        return True
