import logging

from aiogram import F, Router
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.types import CallbackQuery, ChatMemberUpdated
from stp_database import Employee, MainRequestsRepo

from tgbot.keyboards.group.events import RemovedUser, on_user_leave_kb
from tgbot.misc.dicts import group_admin_titles, role_names
from tgbot.misc.helpers import short_name
from tgbot.services.logger import setup_logging

group_events_router = Router()

setup_logging()
logger = logging.getLogger(__name__)


@group_events_router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated, main_repo: MainRequestsRepo):
    user: Employee = await main_repo.employee.get_users(event.new_chat_member.user.id)

    if user is None:
        return

    if user.role not in [2, 3, 10]:
        await event.bot.ban_chat_member(chat_id=event.chat.id, user_id=user.user_id)
        await event.bot.send_message(
            chat_id=event.chat.id,
            text=f"""<b>🙅‍♂️ Исключение</b>

Пользователь <code>{short_name(user.fullname)}</code> исключен
Причина: недостаточно прав для входа""",
            reply_markup=on_user_leave_kb(
                user_id=event.new_chat_member.user.id, change_role=True
            ),
        )
        return

    await event.bot.send_message(
        chat_id=event.chat.id,
        text=f"""<b>❤️‍ Новый пользователь</b>

<b>{short_name(user.fullname)}</b> присоединился к группе

<b>👔 Должность:</b> {user.position}
<b>👑 Руководитель:</b> {user.head}

<i><b>Роль:</b> {role_names[user.role]}</i>""",
    )

    await event.bot.promote_chat_member(
        chat_id=event.chat.id, user_id=user.user_id, can_invite_users=True
    )
    await event.bot.set_chat_administrator_custom_title(
        chat_id=event.chat.id,
        user_id=event.new_chat_member.user.id,
        custom_title=group_admin_titles[user.role],
    )


@group_events_router.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated, main_repo: MainRequestsRepo):
    left_user_id = event.new_chat_member.user.id
    action_user_id = event.from_user.id

    left_user: Employee = await main_repo.employee.get_users(
        event.new_chat_member.user.id
    )
    action_user: Employee = await main_repo.employee.get_users(event.from_user.id)

    if left_user_id == action_user_id:
        # Пользователь вышел сам
        await event.answer(
            text=f"""<b>🚪 Выход</b>

Пользователь <b>{short_name(left_user.fullname)}</b> вышел из группы""",
            reply_markup=on_user_leave_kb(user_id=left_user_id),
        )
    else:
        # Пользователь был кикнут
        await event.answer(
            text=f"""<b>🙅‍♂️ Исключение</b>

Пользователь <b>{short_name(left_user.fullname)}</b> был исключен администратором <code>{action_user.fullname}</code>""",
            reply_markup=on_user_leave_kb(user_id=left_user_id),
        )


@group_events_router.callback_query(RemovedUser.filter(F.action == "change_role"))
async def change_user_role(
    callback: CallbackQuery,
    callback_data: RemovedUser,
    user: Employee,
    main_repo: MainRequestsRepo,
):
    logger.info(callback_data.user_id)
    removed_user: Employee = await main_repo.employee.get_users(callback_data.user_id)

    if user.role == 10 and removed_user:
        await callback.bot.unban_chat_member(
            chat_id=callback.message.chat.id, user_id=callback_data.user_id
        )

        updated_user: Employee = await main_repo.employee.update_user(
            user_id=callback_data.user_id, Role=callback_data.role
        )

        invite_link: str = await callback.bot.export_chat_invite_link(
            chat_id=callback.message.chat.id
        )

        await callback.message.edit_text(
            f"""<b>🟢 Разблокировка</b>

Администратор <b>{short_name(user.fullname)}</b> разблокировал пользователя <b>{updated_user.fullname}</b>

Теперь пользователь имеет роль <b>{role_names[updated_user.role]}</b>

<i>Используйте ссылку <code>{invite_link}</code> для повторного приглашения</i>""",
            reply_markup=on_user_leave_kb(
                user_id=updated_user.user_id, change_role=False
            ),
        )

    else:
        await callback.answer("У тебя недостаточно прав 🥺")
        return
    await callback.answer()
