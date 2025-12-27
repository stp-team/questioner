import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.keyboards.group.main import reopened_question_kb
from tgbot.keyboards.user.main import (
    QuestionQualitySpecialist,
    finish_question_kb,
)
from tgbot.misc.helpers import format_fullname, short_name

user_q_return = Router()
user_q_return.message.filter(F.chat.type == "private")
user_q_return.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@user_q_return.callback_query(QuestionQualitySpecialist.filter(F.return_question))
async def q_return(
    callback: CallbackQuery,
    callback_data: QuestionQualitySpecialist,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
    user: Employee,
):
    """Возврат вопроса специалистом по клику на клавиатуру после закрытия вопроса."""
    active_questions = await questions_repo.questions.get_active_questions()
    question: Question = await questions_repo.questions.get_question(
        token=callback_data.token
    )
    available_to_return_questions = (
        await questions_repo.questions.get_available_to_return_questions()
    )

    if user.user_id in [d.employee_userid for d in active_questions]:
        await callback.answer("У тебя есть другой открытый вопрос", show_alert=True)
        return

    if question.status != "closed":
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        return

    if question.token not in [q.token for q in available_to_return_questions]:
        await callback.answer(
            "Вопрос не переоткрыть. Прошло более 24 часов или возврат заблокирован",
            show_alert=True,
        )
        return

    # Обновляем статус вопроса
    await questions_repo.questions.update_question(
        token=question.token,
        status="open",
    )

    # Обновляем топик
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )
    await callback.bot.edit_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        name=f"{user.division} | {short_name(user.fullname)}"
        if group_settings.get_setting("show_division")
        else short_name(user.fullname),
        icon_custom_emoji_id=group_settings.get_setting("emoji_in_progress"),
    )
    await callback.bot.reopen_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
    )

    # Уведомляем специалиста
    await callback.message.answer(
        """<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""",
        reply_markup=finish_question_kb(),
    )

    # Уведомляем дежурного
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

    await callback.bot.send_message(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        text=f"""<b>🔓 Вопрос переоткрыт</b>

Специалист <b>{format_fullname(user, True, True)}</b> переоткрыл вопрос сразу после закрытия
{duty_info}

❓ <b>Изначальный вопрос:</b>
<blockquote expandable>{question.question_text}</blockquote>""",
        reply_markup=reopened_question_kb(),
        disable_web_page_preview=True,
    )
