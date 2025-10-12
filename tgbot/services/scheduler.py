import datetime
import logging

import pytz
from aiogram import Bot
from aiogram.types import ReplyKeyboardRemove
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Sequence
from stp_database import Employee, MainRequestsRepo, MessagesPair, Question
from stp_database.repo.Questions.requests import QuestionsRequestsRepo

from tgbot.config import load_config
from tgbot.keyboards.group.main import closed_question_duty_kb
from tgbot.keyboards.user.main import closed_question_specialist_kb
from tgbot.services.logger import setup_logging

config = load_config(".env")


scheduler = AsyncIOScheduler()

if config.tg_bot.use_redis:
    job_defaults = {
        "coalesce": True,
        "misfire_grace_time": 300,
        "replace_existing": True,
    }

    REDIS = {
        "host": config.redis.redis_host,
        "port": config.redis.redis_port,
        "password": config.redis.redis_pass,
        "db": 1,
        "ssl": False,
        "decode_responses": False,
    }

    jobstores = {
        "default": MemoryJobStore(),
        "redis": RedisJobStore(**REDIS),
    }

    scheduler.configure(
        jobstores=jobstores,
        job_defaults=job_defaults,
        timezone=pytz.utc,
    )
else:
    jobstores = {
        "default": MemoryJobStore(),
    }

    job_defaults = {
        "coalesce": True,
        "misfire_grace_time": 300,
        "replace_existing": True,
    }

    scheduler.configure(
        jobstores=jobstores,
        job_defaults=job_defaults,
        timezone=pytz.utc,
    )

# TODO ОПТИМИЗИРОВАТЬ

# Global registry to store picklable dependencies
_scheduler_registry = {}

setup_logging()
logger = logging.getLogger(__name__)


def register_scheduler_dependencies(bot, questioner_session_pool):
    """Register bot and session pool for use by scheduled jobs."""
    _scheduler_registry["bot"] = bot
    _scheduler_registry["questioner_session_pool"] = questioner_session_pool


async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]):
    """Удаляет список сообщений."""
    try:
        for message_id in message_ids:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщений: {e}")


async def delete_messages_job(chat_id: int, message_ids: list[int]):
    """Standalone job function to delete messages."""
    try:
        bot = _scheduler_registry.get("bot")
        if not bot:
            logger.error("Bot not registered in scheduler")
            return

        for message_id in message_ids:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщений: {e}")


async def run_delete_timer(chat_id: int, message_ids: list[int], seconds: int = 60):
    """Delete messages after timer. Default - 60 seconds."""
    try:
        scheduler.add_job(
            delete_messages_job,
            "date",
            run_date=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))
            + datetime.timedelta(seconds=seconds),
            args=[chat_id, message_ids],
            jobstore="redis" if config.tg_bot.use_redis else "default",
        )
    except Exception as e:
        logger.error(f"Ошибка при планировании удаления сообщений: {e}")


async def remove_question_timer(question: Question):
    """Schedule question removal after 30 seconds."""
    try:
        warning_job_id = f"remove_{question.token}"
        scheduler.add_job(
            remove_question_job,
            "date",
            run_date=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))
            + datetime.timedelta(seconds=30),
            args=[
                question.group_id,
                question.topic_id,
            ],
            id=warning_job_id,
            jobstore="redis" if config.tg_bot.use_redis else "default",
        )
    except Exception as e:
        logger.error(f"Ошибка при планировании удаления вопроса {question.token}: {e}")


async def remove_question_job(group_id: int, topic_id: int):
    """Standalone job function to remove question topic."""
    try:
        bot = _scheduler_registry.get("bot")
        if not bot:
            logger.error("Bot not registered in scheduler")
            return

        await bot.delete_forum_topic(
            chat_id=group_id,
            message_thread_id=topic_id,
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении топика {topic_id}: {e}")


async def remove_old_topics(bot: Bot, session_pool):
    """Remove old topics and questions."""
    try:
        # Create a session and RequestsRepo instance
        async with session_pool() as session:
            questions_repo = QuestionsRequestsRepo(session)

            old_questions: Sequence[
                Question
            ] = await questions_repo.questions.get_old_questions(days=60)
            old_pairs: Sequence[
                MessagesPair
            ] = await questions_repo.messages_pairs.get_old_pairs()

            questions_result = await questions_repo.questions.delete_question(
                questions=old_questions
            )
            pairs_result = await questions_repo.messages_pairs.delete_pairs(
                pairs=old_pairs
            )

            for question in old_questions:
                try:
                    await bot.delete_forum_topic(
                        chat_id=question.group_id,
                        message_thread_id=question.topic_id,
                    )
                except Exception as e:
                    logger.error(
                        f"[Старые топики] Ошибка при удалении топика {question.topic_id}: {e}"
                    )

            logger.info(
                f"[Старые топики] Успешно удалено {questions_result['deleted_count']} из {questions_result['total_count']} старых вопросов"
            )
            logger.info(
                f"[Старые пары] Успешно удалено {pairs_result['deleted_count']} из {pairs_result['total_count']} старых пар сообщений"
            )

            if questions_result["errors"]:
                logger.info(
                    f"[Старые топики] Произошла ошибка при удалении части вопросов: {questions_result['errors']}"
                )
            if pairs_result["errors"]:
                logger.info(
                    f"[Старые пары] Произошла ошибка при удалении части пар: {pairs_result['errors']}"
                )
    except Exception as e:
        logger.error(f"[Старые топики] Общая ошибка при удалении старых данных: {e}")


async def send_inactivity_warning_job(question_token: str):
    """Standalone function to send inactivity warning."""
    try:
        bot = _scheduler_registry.get("bot")
        questioner_session_pool = _scheduler_registry.get("questioner_session_pool")

        if not bot or not questioner_session_pool:
            logger.error("Bot or questioner_session_pool not registered in scheduler")
            return

        # Create a fresh session for this job
        async with questioner_session_pool() as session:
            questions_repo = QuestionsRequestsRepo(session=session)
            await send_inactivity_warning(bot, question_token, questions_repo)

    except Exception as e:
        logger.error(f"Error in inactivity warning job for {question_token}: {e}")


async def auto_close_question_job(question_token: str):
    """Standalone function to auto-close question."""
    try:
        bot = _scheduler_registry.get("bot")
        questioner_session_pool = _scheduler_registry.get("questioner_session_pool")

        if not bot or not questioner_session_pool:
            logger.error("Bot or questioner_session_pool not registered in scheduler")
            return

        # Create a fresh session for this job
        async with questioner_session_pool() as session:
            questions_repo = QuestionsRequestsRepo(session=session)
            await auto_close_question(bot, question_token, questions_repo)

    except Exception as e:
        logger.error(f"Error in auto-close job for {question_token}: {e}")


async def send_inactivity_warning(
    bot: Bot, question_token: str, questions_repo: QuestionsRequestsRepo
):
    """Отправляет предупреждение о бездействии через 5 минут."""
    try:
        question: Question = await questions_repo.questions.get_question(
            token=question_token
        )
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id,
        )

        if question and question.status in ["open", "in_progress"]:
            # Отправляем предупреждение в топик
            await bot.send_message(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                text=f"⚠️ <b>Внимание!</b>\n\nЧат будет автоматически закрыт через {group_settings.get_setting('activity_warn_minutes')} минут при отсутствии активности",
            )

            # Отправляем предупреждение пользователю
            await bot.send_message(
                chat_id=question.employee_userid,
                text=f"⚠️ <b>Внимание!</b>\n\nТвой вопрос будет автоматически закрыт через {group_settings.get_setting('activity_warn_minutes')} минут при отсутствии активности",
            )

    except Exception as e:
        logger.error(
            f"[Таймер бездействия] Ошибка при отправке предупреждения для вопроса {question_token}: {e}"
        )


async def auto_close_question(
    bot: Bot, question_token: str, questions_repo: QuestionsRequestsRepo
):
    """Автоматически закрывает вопрос через 10 минут бездействия."""
    try:
        question: Question = await questions_repo.questions.get_question(
            token=question_token
        )
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id,
        )

        if question and question.status in ["open", "in_progress"]:
            # Закрываем вопрос
            await questions_repo.questions.update_question(
                token=question.token,
                status="closed",
                end_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
            )

            # Уведомляем о закрытии
            await bot.send_message(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                text=f"🔒 <b>Вопрос автоматически закрыт</b>\n\nВопрос был закрыт из-за отсутствия активности в течение {group_settings.get_setting('activity_close_minutes')} минут",
                reply_markup=closed_question_duty_kb(token=question_token),
            )

            # Обновляем топик
            await bot.edit_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                name=question.token,
                icon_custom_emoji_id=group_settings.get_setting("emoji_closed"),
            )
            await bot.close_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
            )

            await bot.send_message(
                chat_id=question.employee_userid,
                text="🔒 <b>Вопрос автоматически закрыт</b>",
                reply_markup=ReplyKeyboardRemove(),
            )
            await bot.send_message(
                chat_id=question.employee_userid,
                text=f"Твой вопрос был закрыт из-за отсутствия активности в течение {group_settings.get_setting('activity_close_minutes')} минут",
                reply_markup=closed_question_specialist_kb(token=question_token),
            )

    except Exception as e:
        logger.error(
            f"[Таймер бездействия] Ошибка при автоматическом закрытии вопроса {question_token}: {e}"
        )


async def start_inactivity_timer(question_token: str, questions_repo):
    """Запускает таймер бездействия для вопроса."""
    try:
        # Проверяем, нужно ли запускать таймер для этого вопроса
        question = await questions_repo.questions.get_question(token=question_token)
        if not question:
            return
        group_settings = await questions_repo.settings.get_settings_by_group_id(
            group_id=question.group_id,
        )

        # Определяем эффективный статус активности
        activity_enabled = (
            question.activity_status_enabled
            if question.activity_status_enabled is not None
            else group_settings.get_setting("activity_status")
        )
        if not activity_enabled:
            # Если активность отключена для этого топика, не запускаем таймер
            return

        # Удаляем существующие задачи для этого вопроса
        stop_inactivity_timer(question_token)

        # Запускаем таймер предупреждения
        warning_job_id = f"warning_{question_token}"
        scheduler.add_job(
            send_inactivity_warning_job,
            "date",
            run_date=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))
            + datetime.timedelta(
                minutes=int(group_settings.get_setting("activity_warn_minutes"))
            ),
            args=[question_token],
            id=warning_job_id,
            jobstore="redis" if config.tg_bot.use_redis else "default",
        )

        # Запускаем таймер автозакрытия
        close_job_id = f"close_{question_token}"
        scheduler.add_job(
            auto_close_question_job,
            "date",
            run_date=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))
            + datetime.timedelta(
                minutes=int(group_settings.get_setting("activity_close_minutes"))
            ),
            args=[question_token],
            id=close_job_id,
            jobstore="redis" if config.tg_bot.use_redis else "default",
        )

    except Exception as e:
        logger.error(
            f"[Таймер бездействия] Ошибка при запуске таймера для вопроса {question_token}: {e}"
        )


def stop_inactivity_timer(question_token: str):
    """Останавливает таймер бездействия для вопроса."""
    try:
        warning_job_id = f"warning_{question_token}"
        close_job_id = f"close_{question_token}"

        # Удаляем задачи, если они существуют
        try:
            scheduler.remove_job(
                warning_job_id,
                jobstore="redis" if config.tg_bot.use_redis else "default",
            )
        except Exception as e:
            logger.debug(f"[Задачи] Ошибка при удалении задачи {warning_job_id}: {e}")

        try:
            scheduler.remove_job(
                close_job_id, jobstore="redis" if config.tg_bot.use_redis else "default"
            )
        except Exception as e:
            logger.debug(f"[Задачи] Ошибка при удалении задачи {close_job_id}: {e}")

    except Exception as e:
        logger.error(
            f"[Таймер бездействия] Ошибка при остановке таймера для вопроса {question_token}: {e}"
        )


async def restart_inactivity_timer(question_token: str, questions_repo):
    """Перезапускает таймер бездействия для вопроса."""
    try:
        # Останавливаем существующий таймер
        stop_inactivity_timer(question_token)

        # Запускаем новый таймер
        await start_inactivity_timer(question_token, questions_repo)

    except Exception as e:
        logger.error(
            f"[Таймер бездействия] Ошибка при перезапуске таймера для вопроса {question_token}: {e}"
        )


async def send_attention_reminder_job(question_token: str):
    """Standalone function to send attention reminder to general chat."""
    try:
        bot = _scheduler_registry.get("bot")
        questioner_session_pool = _scheduler_registry.get("questioner_session_pool")
        main_session_pool = _scheduler_registry.get("main_session_pool")

        if not bot or not questioner_session_pool:
            logger.error("Bot or questioner_session_pool not registered in scheduler")
            return

        # Create a fresh session for this job
        async with questioner_session_pool() as questioner_session:
            async with main_session_pool() as main_session:
                questions_repo = QuestionsRequestsRepo(session=questioner_session)
                await send_attention_reminder(
                    bot, question_token, questions_repo, main_session
                )

    except Exception as e:
        logger.error(f"Error in attention reminder job for {question_token}: {e}")


async def send_attention_reminder(
    bot: Bot,
    question_token: str,
    questions_repo: QuestionsRequestsRepo,
    main_repo: MainRequestsRepo,
):
    """Отправляет напоминание о вопросе, требующем внимания, в общий чат группы."""
    try:
        question: Question = await questions_repo.questions.get_question(
            token=question_token
        )
        employee: Employee = await main_repo.employee.get_users(
            user_id=question.employee_userid
        )

        if not question:
            logger.warning(
                f"[Внимание вопросу] Вопрос {question_token} не найден в базе для напоминания"
            )
            stop_attention_reminder(question_token)
            return

        # Проверка, что вопрос все еще открыт и не имеет дежурного
        if question.status != "open" or question.duty_userid:
            logger.info(
                f"[Внимание вопросу] Вопрос {question_token} уже имеет дежурного или закрыт, пропускаем напоминание"
            )
            stop_attention_reminder(question.token)
            return

        # Отправка уведомления в главную тему
        reminder_text = f"""🔔 <b>Вопрос требует внимания!</b>

<b>От:</b> {employee.fullname}
<b>Создан в:</b> {question.start_time.strftime("%H:%M")} ПРМ

Вопрос ожидает дежурного уже 5 минут!

<a href="https://t.me/c/{str(question.group_id)[4:]}/{question.topic_id}">Перейти к вопросу</a>"""

        await bot.send_message(
            chat_id=question.group_id,
            text=reminder_text,
            disable_web_page_preview=True,
        )

        logger.info(
            f"[Внимание вопросу] Напоминание отправлено по вопросу {question_token}"
        )

    except Exception as e:
        logger.error(
            f"[Внимание вопросу] Ошибка при отправке напоминания для вопроса {question_token}: {e}"
        )


async def start_attention_reminder(question_token: str, questions_repo):
    """Запускает таймер напоминаний о внимании для нового вопроса."""
    try:
        question = await questions_repo.questions.get_question(token=question_token)
        if not question:
            stop_attention_reminder(question.token)
            return

        # Проверка, что вопрос все еще открыт и не имеет дежурного
        if question.status != "open" or question.duty_userid:
            stop_attention_reminder(question.token)
            return

        # Останавливаем все активные напоминания для этого вопроса
        stop_attention_reminder(question_token)

        # Запускаем рекуррентную задачу для проверки каждые 5 минут
        attention_job_id = f"attention_reminder_{question_token}"
        scheduler.add_job(
            send_attention_reminder_job,
            "interval",
            minutes=5,
            start_date=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))
            + datetime.timedelta(minutes=5),
            args=[question_token],
            id=attention_job_id,
            jobstore="redis" if config.tg_bot.use_redis else "default",
        )

        logger.info(
            f"[Внимание вопросу] Отслеживание дежурного включено для вопроса {question_token}"
        )

    except Exception as e:
        logger.error(
            f"[Внимание вопросу] Ошибка при запуске отслеживания дежурного для вопроса {question_token}: {e}"
        )


def stop_attention_reminder(question_token: str):
    """Останавливает таймер напоминаний о внимании для вопроса."""
    try:
        attention_job_id = f"attention_reminder_{question_token}"

        # Удаляем задачу если найдена
        try:
            scheduler.remove_job(
                attention_job_id,
                jobstore="redis" if config.tg_bot.use_redis else "default",
            )
            logger.info(
                f"[Внимание вопросу] Отслеживание выключено для вопроса {question_token}"
            )
        except Exception as e:
            logger.debug(f"[Задачи] Ошибка при удалении задачи {attention_job_id}: {e}")

    except Exception as e:
        logger.error(
            f"[Напоминание о внимании] Ошибка при остановке напоминаний для вопроса {question_token}: {e}"
        )
