import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message
from stp_database.models.Questions import MessagesPair
from stp_database.repo.Questions import QuestionsRequestsRepo

from tgbot.services.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class MessagePairingMiddleware(BaseMiddleware):
    """Middleware to handle message pairing for edited messages.

    This middleware finds the corresponding message pair when a message is edited,
    allowing handlers to edit the correct message instead of sending a new one.
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Процессим только измененные сообщения
        if not (hasattr(event, "edit_date") and event.edit_date):
            return await handler(event, data)

        # Получаем репозиторий из данных (должно быть предоставлено DatabaseMiddleware)
        questions_repo: QuestionsRequestsRepo = data.get("questions_repo")
        if not questions_repo:
            logger.error("MessagePairingMiddleware: No repository found in data")
            return await handler(event, data)

        try:
            # Find the corresponding message pair for editing
            connection: MessagesPair = (
                await questions_repo.messages_pairs.find_pair_for_edit(
                    chat_id=event.chat.id, message_id=event.message_id
                )
            )

            if connection:
                # Determine target chat and message for editing
                if event.chat.id == connection.user_chat_id:
                    # Editing from user side -> target is topic
                    data["edit_target_chat_id"] = connection.topic_chat_id
                    data["edit_target_message_id"] = connection.topic_message_id
                    data["edit_target_thread_id"] = connection.topic_thread_id
                    data["edit_direction"] = "user_to_topic"
                else:
                    # Editing from topic side -> target is user
                    data["edit_target_chat_id"] = connection.user_chat_id
                    data["edit_target_message_id"] = connection.user_message_id
                    data["edit_target_thread_id"] = None
                    data["edit_direction"] = "topic_to_user"

                data["message_connection"] = connection
                logger.info(
                    f"[Редактирование]: Найдена пара для редактирования {event.chat.id}:{event.message_id} -> "
                    f"{data['edit_target_chat_id']}:{data['edit_target_message_id']}"
                )
            else:
                # Пара не найдена - скорее всего сообщение не было записано в БД
                logger.warning(
                    f"[Редактирование]: Не найдена пара для редактирования: {event.chat.id}:{event.message_id}"
                )
                data["edit_target_chat_id"] = None
                data["edit_target_message_id"] = None

        except Exception as e:
            logger.error(f"Error in MessagePairingMiddleware: {e}")
            data["edit_target_chat_id"] = None
            data["edit_target_message_id"] = None

        return await handler(event, data)


async def store_message_connection(
    questions_repo: QuestionsRequestsRepo,
    user_chat_id: int,
    user_message_id: int,
    topic_chat_id: int,
    topic_message_id: int,
    topic_thread_id: int,
    question_token: str,
    direction: str,
) -> MessagesPair:
    """Helper function to store message connection in database.

    Args:
        questions_repo: Repository instance
        user_chat_id: Employee chat ID
        user_message_id: Message ID in user chat
        topic_chat_id: Forum chat ID
        topic_message_id: Message ID in forum topic
        topic_thread_id: Thread ID in forum topic
        question_token: Associated question token
        direction: 'user_to_topic' or 'topic_to_user'

    Returns:
        Created MessageConnection instance
    """
    try:
        connection = await questions_repo.messages_pairs.add_pair(
            user_chat_id=user_chat_id,
            user_message_id=user_message_id,
            topic_chat_id=topic_chat_id,
            topic_message_id=topic_message_id,
            topic_thread_id=topic_thread_id,
            question_token=question_token,
            direction=direction,
        )
        logger.info(
            f"[Редактирование] Сохраняем пару из сообщений: {direction} - "
            f"юзер:{user_chat_id}:{user_message_id} <-> "
            f"топик:{topic_chat_id}:{topic_message_id}"
        )
        return connection
    except Exception as e:
        logger.error(f"Failed to store message connection: {e}")
        raise
