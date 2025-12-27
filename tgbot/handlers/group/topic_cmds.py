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
from tgbot.keyboards.group.main import FinishedQuestion, question_quality_duty_kb
from tgbot.keyboards.user.main import question_quality_specialist_kb
from tgbot.misc.helpers import short_name
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import (
    start_attention_reminder,
    stop_inactivity_timer,
)

topic_cmds_router = Router()

setup_logging()
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

    if question is not None:
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id,
        )

        if question.status != "closed" and (
            question.duty_userid == user.user_id or user.role == 10
        ):
            # Останавливаем таймер бездействия
            stop_inactivity_timer(question.token)

            await questions_repo.questions.update_question(
                token=question.token,
                status="closed",
                end_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
            )

            if question.quality_duty is not None:
                if question.quality_duty:
                    await message.bot.send_message(
                        chat_id=question.group_id,
                        message_thread_id=question.topic_id,
                        text=f"""<b>🔒 Вопрос закрыт</b>

👮‍♂️ Дежурный: <b>{user.fullname if user.fullname else "Не закреплен"}</b>
👍 Специалист <b>не мог решить вопрос самостоятельно</b>""",
                        reply_markup=question_quality_duty_kb(
                            token=question.token,
                            show_quality=None,
                            allow_return=question.allow_return,
                        ),
                    )
                else:
                    await message.bot.send_message(
                        chat_id=question.group_id,
                        message_thread_id=question.topic_id,
                        text=f"""<b>🔒 Вопрос закрыт</b>
                        
👮‍♂️ Дежурный: <b>{user.fullname}</b>
👎 Специалист <b>мог решить вопрос самостоятельно</b>""",
                        reply_markup=question_quality_duty_kb(
                            token=question.token,
                            show_quality=None,
                            allow_return=question.allow_return,
                        ),
                    )
            else:
                await message.bot.send_message(
                    chat_id=question.group_id,
                    message_thread_id=question.topic_id,
                    text=f"""<b>🔒 Вопрос закрыт</b>
                    
👮‍♂️ Дежурный: <b>{user.fullname}</b>
Оцени, мог ли специалист решить его самостоятельно""",
                    reply_markup=question_quality_duty_kb(
                        token=question.token,
                        show_quality=True,
                        allow_return=question.allow_return,
                    ),
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

            employee: Employee = await stp_repo.employee.get_users(
                user_id=question.employee_userid
            )

            await message.bot.send_message(
                chat_id=employee.user_id,
                text="<b>🔒 Вопрос закрыт</b>",
                reply_markup=ReplyKeyboardRemove(),
            )

            await message.bot.send_message(
                chat_id=employee.user_id,
                text=f"""Дежурный <b>{short_name(user.fullname)}</b> закрыл вопрос
Оцени, помогли ли тебе решить его""",
                reply_markup=question_quality_specialist_kb(token=question.token),
            )

            logger.info(
                f"[Вопрос] - [Закрытие] Пользователь {message.from_user.username} ({message.from_user.id}): Закрыт вопрос {question.token} со специалистом {question.employee_userid}"
            )
        elif question.status != "closed" and question.duty_userid != user.user_id:
            await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится специалисту</i>""")
            logger.warning(
                f"[Вопрос] - [Закрытие] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка закрытия вопроса {question.token} неуспешна. Вопрос принадлежит другому дежурному"
            )
        elif question.status == "closed":
            await message.bot.edit_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                name=question.token,
                icon_custom_emoji_id=group_settings.get_setting("emoji_closed"),
            )
            await message.reply("<b>🔒 Вопрос был закрыт</b>")
            await message.bot.close_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
            )
            logger.warning(
                f"[Вопрос] - [Закрытие] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка закрытия вопроса {question.token} неуспешна. Вопрос уже закрыт"
            )

    else:
        await message.answer("""<b>⚠️ Ошибка</b>

Не удалось найти текущую тему в базе""")
        logger.error(
            f"[Вопрос] - [Закрытие] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка закрытия вопроса неуспешна. Не удалось найти вопрос в базе с TopicId = {message.message_id}"
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

    if question is not None:
        if question.duty_userid is not None and (
            question.duty_userid == user.user_id or user.role == 10
        ):
            group_settings = await questions_repo.settings.get_settings_by_group_id(
                group_id=question.group_id,
            )

            await questions_repo.questions.update_question(
                token=question.token,
                duty_userid=None,
                status="open",
            )

            employee: Employee = await stp_repo.employee.get_users(
                user_id=question.employee_userid
            )

            await message.bot.edit_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                icon_custom_emoji_id=group_settings.get_setting("emoji_open"),
            )
            await message.answer("""<b>🕊️ Вопрос освобожден</b>

Для взятия вопроса в работу напиши сообщение в эту тему""")

            await message.bot.send_message(
                chat_id=employee.user_id,
                text=f"""<b>🕊️ Дежурный покинул чат</b>

Дежурный <b>{short_name(user.fullname)}</b> освободил вопрос. Ожидай повторного подключения старшего""",
            )
            await start_attention_reminder(question.token, questions_repo)
            logger.info(
                f"[Вопрос] - [Освобождение] Пользователь {message.from_user.username} ({message.from_user.id}): Вопрос {question.token} освобожден"
            )
        elif question.duty_userid and question.duty_userid != user.user_id:
            await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится специалисту</i>""")
            logger.warning(
                f"[Вопрос] - [Освобождение] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка закрытия вопроса {question.token} неуспешна. Вопрос принадлежит другому старшему"
            )
        elif question.duty_userid is None:
            await message.reply("""<b>⚠️ Предупреждение</b>

Это чат сейчас никем не занят!""")
            logger.warning(
                f"[Вопрос] - [Освобождение] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка освобождения вопроса {question.token} неуспешна. Вопрос {question.token} никем не занят"
            )
    else:
        await message.answer("""<b>⚠️ Ошибка</b>

Не удалось найти текущую тему в базе, закрываю""")
        await message.bot.close_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
        )
        logger.error(
            f"[Вопрос] - [Освобождение] Пользователь {message.from_user.username} ({message.from_user.id}): Попытка освобождения вопроса неуспешна. Не удалось найти вопрос в базе с TopicId = {message.message_thread_id}"
        )


@topic_cmds_router.callback_query(FinishedQuestion.filter(F.action == "release"))
async def release_q_cb(
    callback: CallbackQuery,
    questions_repo: QuestionsRequestsRepo,
):
    await callback.answer()

    question: Question = await questions_repo.questions.get_question(
        group_id=callback.message.chat.id, topic_id=callback.message.message_thread_id
    )

    if question:
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id,
        )

        await questions_repo.questions.update_question(
            token=question.token,
            duty_userid=None,
            status="open",
        )

        await callback.message.answer("""<b>🕊️ Вопрос освобожден</b>

Для взятия вопроса в работу напиши сообщение в эту тему""")
        logger.info(
            f"[Вопрос] - [Освобождение] Пользователь {callback.from_user.username} ({callback.from_user.id}): Вопрос {question.token} освобожден"
        )

        await callback.bot.edit_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            icon_custom_emoji_id=group_settings.get_setting("emoji_open"),
        )

        await start_attention_reminder(question.token, questions_repo)
