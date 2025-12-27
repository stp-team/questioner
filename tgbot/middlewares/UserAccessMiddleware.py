import logging
from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message
from stp_database.models.STP import Employee
from stp_database.repo.STP import MainRequestsRepo

logger = logging.getLogger(__name__)


class UserAccessMiddleware(BaseMiddleware):
    """Middleware responsible for updating user information."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[
            [Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]
        ],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        # Get user and repos from previous middleware (DatabaseMiddleware)
        user: Employee = data.get("user")
        stp_repo: MainRequestsRepo = data.get("stp_repo")

        # Update username if needed
        await self._update_username(user, event, stp_repo)

        return await handler(event, data)

    @staticmethod
    async def _update_username(
        user: Employee,
        event: Union[Message, CallbackQuery],
        stp_repo: MainRequestsRepo,
    ):
        """Обновление юзернейма пользователя если он отличается от записанного
        :param user:
        :param event:
        :param stp_repo:
        :return:
        """
        if not user:
            return

        current_username = event.from_user.username
        stored_username = user.username

        if stored_username != current_username:
            try:
                if current_username is None:
                    await stp_repo.employee.update_user(
                        user_id=event.from_user.id,
                        username=None,
                    )
                    logger.info(
                        f"[Юзернейм] Удален юзернейм пользователя {event.from_user.id}"
                    )
                else:
                    await stp_repo.employee.update_user(
                        user_id=event.from_user.id, username=current_username
                    )
                    logger.info(
                        f"[Юзернейм] Обновлен юзернейм пользователя {event.from_user.id} - @{current_username}"
                    )
            except Exception as e:
                logger.error(
                    f"[Юзернейм] Ошибка обновления юзернейма для пользователя {event.from_user.id}: {e}"
                )
