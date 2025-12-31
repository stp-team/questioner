import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, TelegramObject
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.config import Config

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Middleware responsible only for database connections and session management.
    Provides database repositories to other middlewares and handlers.
    """

    def __init__(
        self, config: Config, bot: Bot, main_session_pool, questioner_session_pool
    ) -> None:
        self.main_session_pool = main_session_pool
        self.questioner_session_pool = questioner_session_pool
        self.bot = bot
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Use separate sessions for different databases
                async with self.main_session_pool() as main_session:
                    async with self.questioner_session_pool() as questioner_session:
                        # Create repositories for different databases
                        stp_repo = MainRequestsRepo(main_session)
                        questioner_repo = QuestionsRequestsRepo(questioner_session)

                        # Get user from database
                        user = await stp_repo.employee.get_users(
                            user_id=event.from_user.id
                        )

                        # Add repositories and user to data for other middlewares
                        data["stp_repo"] = stp_repo
                        data["main_session"] = main_session
                        data["questioner_session"] = questioner_session
                        data["questions_repo"] = questioner_repo
                        data["user"] = user

                        # Continue to the next middleware/handler
                        result = await handler(event, data)
                        return result

            except (OperationalError, DBAPIError, DisconnectionError) as e:
                logger.error(f"[DatabaseMiddleware] Critical database error: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None

        return None
