import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
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
from tgbot.misc.helpers import short_name

emp_q_return_router = Router()
emp_q_return_router.message.filter(F.chat.type == "private")
emp_q_return_router.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@emp_q_return_router.callback_query(QuestionQualitySpecialist.filter(F.return_question))
async def q_return(
    callback: CallbackQuery,
    callback_data: QuestionQualitySpecialist,
    state: FSMContext,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
    user: Employee,
):
    """Возврат вопроса специалистом по клику на клавиатуру после закрытия вопроса."""
    await state.clear()

    active_questions: Sequence[
        Question
    ] = await questions_repo.questions.get_active_questions()
    question: Question = await questions_repo.questions.get_question(
        callback_data.token
    )
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )
    available_to_return_questions: Sequence[
        Question
    ] = await questions_repo.questions.get_available_to_return_questions()

    if (
        question.status == "closed"
        and user.user_id not in [d.employee_userid for d in active_questions]
        and question.token in [d.token for d in available_to_return_questions]
    ):
        duty: Employee = await stp_repo.employee.get_users(user_id=question.duty_userid)
        await questions_repo.questions.update_question(
            token=question.token,
            status="open",
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

        await callback.message.answer(
            """<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""",
            reply_markup=finish_question_kb(),
        )

        duty_info = ""
        if duty:
            duty_info = f"\n<b>👮‍♂️ Дежурный:</b> {duty.fullname}{'\n<span class="tg-spoiler">@' + duty.username + '</span>' if duty.username != 'Не указан' or 'Скрыто/не определено' else ''}"

        await callback.bot.send_message(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

Специалист <b>{short_name(user.fullname)}</b> переоткрыл вопрос сразу после закрытия
{duty_info}

<b>❓ Изначальный вопрос:</b>
<blockquote expandable><i>{question.question_text}</i></blockquote>""",
            reply_markup=reopened_question_kb(),
            disable_web_page_preview=True,
        )
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Вопрос {question.token} переоткрыт специалистом"
        )
    elif user.user_id in [d.employee_userid for d in active_questions]:
        await callback.answer("У тебя есть другой открытый вопрос", show_alert=True)
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у специалиста есть другой открытый вопрос"
        )
    elif question.status != "closed":
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.token} не закрыт"
        )
    elif question.token not in [d.token for d in available_to_return_questions]:
        await callback.answer(
            "Вопрос не переоткрыть. Прошло более 24 часов или возврат заблокирован",
            show_alert=True,
        )
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.token} был закрыт более 24 часов назад или заблокирован"
        )
    await callback.answer()
