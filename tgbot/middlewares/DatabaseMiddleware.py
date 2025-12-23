import logging
from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.config import Config
from tgbot.services.logger import setup_logging

setup_logging()
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
        handler: Callable[
            [Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]
        ],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Use separate sessions for different databases
                async with self.main_session_pool() as main_session:
                    async with self.questioner_session_pool() as questioner_session:
                        # Create repositories for different databases
                        main_repo = MainRequestsRepo(main_session)  # For STPMain DB
                        questioner_repo = QuestionsRequestsRepo(
                            questioner_session
                        )  # For QuestionerBot DB

                        # Get user from database
                        user = await main_repo.employee.get_users(
                            user_id=event.from_user.id
                        )

                        # Add repositories and user to data for other middlewares
                        data["main_repo"] = main_repo
                        data["main_session"] = main_session
                        data["questioner_session"] = questioner_session
                        data["questions_repo"] = questioner_repo
                        data["user"] = user

                        # Continue to the next middleware/handler
                        result = await handler(event, data)
                        return result

            except (OperationalError, DBAPIError, DisconnectionError) as e:
                if "Connection is busy" in str(e) or "HY000" in str(e):
                    retry_count += 1
                    logger.warning(
                        f"[DatabaseMiddleware] Database connection error, retry {retry_count}/{max_retries}: {e}"
                    )
                    if retry_count >= max_retries:
                        logger.error(
                            f"[DatabaseMiddleware] All database connection attempts exhausted: {e}"
                        )
                        if isinstance(event, Message):
                            await event.reply(
                                "⚠️ Временные проблемы с базой данных. Попробуйте позже."
                            )
                        return None
                else:
                    logger.error(f"[DatabaseMiddleware] Critical database error: {e}")
                    return None
            except Exception as e:
                logger.error(f"[DatabaseMiddleware] Unexpected error: {e}")
                return None

        return None
