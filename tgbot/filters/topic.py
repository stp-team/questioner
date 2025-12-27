import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

from tgbot.config import load_config

config = load_config(".env")

logger = logging.getLogger(__name__)


class IsTopicMessage(BaseFilter):
    """Passes only for user messages that belong to a forum‑topic thread."""

    async def __call__(self, message: Message, **_) -> bool:
        # Проверка на группу или супергруппу
        if message.chat.type not in ["supergroup", "group"]:
            return False

        # Проверка на тему
        in_topic = bool(
            message.is_topic_message
            and message.message_thread_id
            and message.message_thread_id != 1
        )

        if not in_topic:
            return False

        # Игнорирование сервисных сообщений
        if message.from_user is None:
            return False

        # Игнорирование сообщений самого бота
        if message.from_user.id == message.bot.id:
            return False

        return True


class IsTopicMessageWithCommand(BaseFilter):
    def __init__(self, command: str = None):
        self.command = command

    async def __call__(self, message: Message, **_) -> bool:
        if self.command:
            if not message.text or not message.text.startswith(f"/{self.command}"):
                return False

        # Проверка на группу или супергруппу
        if message.chat.type not in ["supergroup", "group"]:
            return False

        # Проверка на тему
        in_topic = bool(
            message.is_topic_message
            and message.message_thread_id
            and message.message_thread_id != 1
        )
        if not in_topic:
            return False

        # Игнорирование сервисных сообщений
        if message.from_user is None:
            return False

        # Игнорирование сообщений самого бота
        if message.from_user.id == message.bot.id:
            return False

        return True


class IsMainTopicMessageWithCommand(BaseFilter):
    def __init__(self, command: str = None):
        self.command = command

    async def __call__(self, message: Message, **_) -> bool:
        if self.command:
            if not message.text or not message.text.startswith(f"/{self.command}"):
                return False

        # Проверка на группу или супергруппу
        if message.chat.type not in ["supergroup", "group"]:
            return False

        # Проверка на тему
        in_topic = bool(
            str(message.chat.id)
            in [
                config.forum.ntp_main_forum_id,
                config.forum.ntp_trainee_forum_id,
                config.forum.nck_main_forum_id,
                config.forum.nck_trainee_forum_id,
            ]
            and not message.message_thread_id
        )
        if not in_topic:
            return False

        # Игнорирование сервисных сообщений
        if message.from_user is None:
            return False

        # Игнорирование сообщений самого бота
        if message.from_user.id == message.bot.id:
            return False

        return True
