import logging
from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    ChatMemberAdministrator,
    ChatMemberOwner,
    Message,
)
from stp_database.models.STP import Employee

from tgbot.misc.helpers import get_role

logger = logging.getLogger(__name__)


class AdminRoleMiddleware(BaseMiddleware):
    """Middleware responsible for managing user admin roles and custom titles.
    Ensures users have correct admin permissions and titles based on their role.
    """

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
        # Получаем юзера из прошлой middleware
        user: Employee = data.get("user")

        # Получаем чат из ивента
        chat = (
            event.chat
            if isinstance(event, Message)
            else event.message.chat
            if event.message
            else None
        )

        # Пропускам если не нашли пользователя, пользователь - бот, чат приватный, или чат не найден
        if not user or event.from_user.is_bot or not chat or chat.type == "private":
            return await handler(event, data)

        try:
            # Получаем текущих администраторов
            chat_admins = await self.bot.get_chat_administrators(chat_id=chat.id)

            # Проверяем является ли текущий пользователь администратором чата
            user_admin_status = self._find_user_admin_status(
                chat_admins, event.from_user.id
            )

            if user_admin_status:
                # Если пользователь уже админ, проверяем/обновляем кастомный титул
                await self._update_admin_title_if_needed(
                    user_admin_status, user, chat.id
                )
            else:
                # Если пользователь не админ - промоутим его
                await self._promote_user_to_admin(user, chat.id)

        except Exception as e:
            logger.error(f"[AdminRoleMiddleware] Ошибка менеджмента роли: {e}")
            # Продолжаем даже если менеджмент зафейлился

        return await handler(event, data)

    @staticmethod
    def _find_user_admin_status(chat_admins, user_id: int):
        """Проверка является ли пользователем администратором чата
        :param chat_admins:
        :param user_id:
        :return:
        """
        for admin in chat_admins:
            if admin.user.id == user_id:
                return admin
        return None

    async def _update_admin_title_if_needed(
        self,
        admin_status: Union[ChatMemberOwner, ChatMemberAdministrator],
        user: Employee,
        chat_id: int,
    ):
        """Update admin custom title if it doesn't match user's role"""
        expected_title = get_role(role_id=user.role)["name"]

        # Пропускаем апдейт титула для создателя чата
        if admin_status.status == ChatMemberStatus.CREATOR:
            return

        # Проверяем нужно ли обновлять титул
        if (
            hasattr(admin_status, "custom_title")
            and admin_status.custom_title != expected_title
        ):
            try:
                await self.bot.set_chat_administrator_custom_title(
                    chat_id=chat_id,
                    user_id=user.user_id,
                    custom_title=expected_title,
                )
                logger.info(
                    f"[Роли] Обновлена роль для пользователя {user.fullname} - {expected_title}"
                )
            except TelegramBadRequest:
                logger.error(
                    f"[Роли] Ошибка обновления роли для {user.fullname}: Недостаточно прав для изменения пользователя"
                )
            except Exception as e:
                logger.error(f"[Роли] Ошибка обновления роли для {user.fullname}: {e}")

    async def _promote_user_to_admin(self, user: Employee, chat_id: int) -> None:
        """Повышение пользователя до админа с правами приглашения других пользователей и титулом

        :param user: Модель пользователя из БД
        :param chat_id: Идентификатор чата Telegram
        """
        try:
            # Promote user to admin
            await self.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user.user_id,
                can_invite_users=True,
            )

            # Set custom title
            expected_title = get_role(role_id=user.role)["name"]
            if expected_title:
                await self.bot.set_chat_administrator_custom_title(
                    chat_id=chat_id,
                    user_id=user.user_id,
                    custom_title=expected_title,
                )

            logger.info(
                f"[Роли] Обновлена роль для пользователя {user.fullname} - {expected_title}. "
                f"Пользователь повышен до администратора"
            )

        except Exception as e:
            logger.error(f"[Роли] Ошибка повышения пользователя {user.fullname}: {e}")
