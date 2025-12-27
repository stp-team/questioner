import datetime
import logging

import pytz
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from stp_database.models.Questions import Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.filters.topic import IsTopicMessageWithCommand
from tgbot.keyboards.group.main import FinishedQuestion, question_finish_duty_kb
from tgbot.keyboards.user.main import question_finish_employee_kb
from tgbot.misc.helpers import format_fullname
from tgbot.services.scheduler import (
    start_attention_reminder,
    stop_inactivity_timer,
)

topic_cmds_router = Router()

logger = logging.getLogger(__name__)


@topic_cmds_router.message(IsTopicMessageWithCommand("end"))
async def end_q_cmd(
    message: Message,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=message.chat.id, topic_id=message.message_thread_id
    )

    if not question:
        await message.answer("""<b>⚠️ Предупреждение</b>
        
Не удалось найти закрываемый вопрос""")
        return

    if question.status == "closed":
        await message.reply("""<b>⚠️ Предупреждение</b>

Вопрос уже закрыт""")
        return

    if question.duty_userid != user.user_id:
        await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится специалисту</i>""")
        return

    # Останавливаем таймер бездействия
    stop_inactivity_timer(question.token)

    # Обновляем статус вопроса
    await questions_repo.questions.update_question(
        token=question.token,
        end_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
        status="closed",
    )

    # Уведомляем дежурного
    await message.answer(
        text=f"""🔒 <b>Вопрос закрыт</b>

👮‍♂️ Дежурный: <b>{format_fullname(user, True, True)}</b>

<i>Токен вопроса: <code>{question.token}</code></i>""",
        reply_markup=question_finish_duty_kb(
            question=question,
        ),
    )

    # Уведомляем специалиста
    employee = await stp_repo.employee.get_users(user_id=question.employee_userid)
    await message.bot.send_message(
        chat_id=employee.user_id,
        text="<b>🔒 Вопрос закрыт</b>",
        reply_markup=ReplyKeyboardRemove(),
    )

    await message.bot.send_message(
        chat_id=employee.user_id,
        text=f"""Дежурный <b>{format_fullname(user, True, True)}</b> закрыл вопрос

Оцени, помогли ли тебе решить его""",
        reply_markup=question_finish_employee_kb(question=question),
    )

    # Закрываем топик
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )
    await message.bot.edit_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        name=question.token,
        icon_custom_emoji_id=group_settings.get_setting("emoji_closed"),
    )
    await message.bot.close_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
    )


@topic_cmds_router.message(IsTopicMessageWithCommand("release"))
async def release_q_cmd(
    message: Message,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=message.chat.id, topic_id=message.message_thread_id
    )

    if not question:
        await message.answer("""<b>⚠️ Предупреждение</b>

Не удалось найти закрываемый вопрос""")
        return

    if not question.duty_userid:
        await message.reply("""<b>⚠️ Предупреждение</b>

Это чат сейчас никем не занят!""")
        return

    if question.duty_userid != user.user_id and user.role != 10:
        await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится специалисту</i>""")
        return

    # Обновляем статус вопроса
    await questions_repo.questions.update_question(
        token=question.token,
        duty_userid=None,
        status="open",
    )

    # Обновляем эмодзи топика
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )
    await message.bot.edit_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        icon_custom_emoji_id=group_settings.get_setting("emoji_open"),
    )

    # Уведомляем дежурных
    await message.answer("""<b>🕊️ Вопрос освобожден</b>

Для взятия вопроса в работу напиши сообщение в эту тему""")

    # Уведомляем специалиста
    employee: Employee = await stp_repo.employee.get_users(
        user_id=question.employee_userid
    )
    await message.bot.send_message(
        chat_id=employee.user_id,
        text=f"""<b>🕊️ Дежурный покинул чат</b>

Дежурный <b>{format_fullname(user, True, True)}</b> освободил вопрос. Ожидай повторного подключения дежурного""",
    )

    # Запускаем таймер внимания
    await start_attention_reminder(question.token, questions_repo)


@topic_cmds_router.callback_query(FinishedQuestion.filter(F.action == "release"))
async def release_q_cb(
    event: CallbackQuery,
    questions_repo: QuestionsRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=event.message.chat.id, topic_id=event.message.message_thread_id
    )

    if not question:
        await event.message.answer("""<b>⚠️ Предупреждение</b>

Не удалось найти закрываемый вопрос""")
        return

    # Обновляем статус вопроса
    await questions_repo.questions.update_question(
        token=question.token,
        duty_userid=None,
        status="open",
    )

    # Уведомляем дежурных
    await event.message.answer("""<b>🕊️ Вопрос освобожден</b>

Для взятия вопроса в работу напишите сообщение в эту тему""")

    # Обновляем эмодзи топика
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )
    await event.bot.edit_forum_topic(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        icon_custom_emoji_id=group_settings.get_setting("emoji_open"),
    )

    # Запускаем таймер внимания
    await start_attention_reminder(question.token, questions_repo)
