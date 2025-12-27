import logging
from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.dialogs.states.user.main import ReturnSG
from tgbot.keyboards.group.main import reopened_question_kb
from tgbot.misc.helpers import format_fullname, short_name

logger = logging.getLogger(__name__)


async def start_q_return_dialog(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(ReturnSG.menu)


async def on_question_select(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager, item_id: str
):
    """Обработчик выбора вопроса для возврата.

    Args:
        _event: Callback query from telegram
        _widget: Widget that triggered the event
        dialog_manager: Dialog manager instance
        item_id: ID of selected question
    """
    dialog_manager.dialog_data["question_token"] = item_id
    await dialog_manager.switch_to(ReturnSG.confirmation)


async def on_confirm_return(
    event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    """Обработчик подтверждения возврата вопроса.

    Args:
        event: Callback query from telegram
        _widget: Widget that triggered the event
        dialog_manager: Dialog manager instance
    """
    question_token = dialog_manager.dialog_data.get("question_token")
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data.get("stp_repo")
    questions_repo: QuestionsRequestsRepo = dialog_manager.middleware_data.get(
        "questions_repo"
    )
    user: Employee = dialog_manager.middleware_data.get("user")

    question: Question = await questions_repo.questions.get_question(
        token=question_token
    )
    active_questions = await questions_repo.questions.get_active_questions()

    if user.user_id in [q.employee_userid for q in active_questions]:
        await event.answer("У тебя есть другой открытый вопрос", show_alert=True)
        return

    if question.status != "closed":
        await event.answer("Этот вопрос не закрыт", show_alert=True)
        return

    if not question.allow_return:
        await event.answer("Возврат вопроса заблокирован", show_alert=True)

    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )

    # Обновляем статус вопроса
    await questions_repo.questions.update_question(token=question_token, status="open")

    try:
        # Редактируем название темы
        await event.bot.edit_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            name=f"{user.division} | {short_name(user.fullname)}"
            if group_settings.get_setting("show_division")
            else short_name(user.fullname),
            icon_custom_emoji_id=group_settings.get_setting("emoji_in_progress"),
        )

        # Открываем топик
        await event.bot.reopen_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
        )
    except Exception:
        logger.warning("Ошибка переоткрытия топика при возврате вопроса")

    # Информируем специалиста
    await event.message.answer("""🔓 <b>Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""")

    # Информируем дежурного
    duty = (
        await stp_repo.employee.get_users(user_id=question.duty_userid)
        if question.duty_userid
        else None
    )
    duty_info = (
        f"👮‍♂️ <b>Дежурный:</b> <b>{format_fullname(duty, True, True)}</b>"
        if duty
        else None
    )

    await event.bot.send_message(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        text=f"""🔓 <b>Вопрос переоткрыт</b>

Специалист <b>{format_fullname(user, True, True)}</b> переоткрыл вопрос

{duty_info}

❓ <b>Изначальный вопрос:</b>
<blockquote expandable>{question.question_text}</blockquote>""",
        reply_markup=reopened_question_kb(),
    )

    await dialog_manager.done(show_mode=ShowMode.NO_UPDATE)
    await event.message.delete()
