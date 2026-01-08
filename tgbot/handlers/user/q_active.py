import datetime
import logging

import pytz
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyKeyboardRemove,
)
from stp_database.models.Questions import MessagesPair, Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo

from tgbot.filters.active_question import ActiveQuestion, ActiveQuestionWithCommand
from tgbot.keyboards.group.main import question_finish_duty_kb
from tgbot.keyboards.user.main import (
    QuestionQualitySpecialist,
    question_finish_employee_kb,
)
from tgbot.middlewares.MessagePairingMiddleware import store_message_connection
from tgbot.misc.helpers import check_premium_emoji, format_fullname, short_name
from tgbot.services.scheduler import (
    restart_inactivity_timer,
    run_delete_timer,
    stop_inactivity_timer,
)

user_q = Router()
user_q.message.filter(F.chat.type == "private")
user_q.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@user_q.message(ActiveQuestionWithCommand("end"))
async def active_question_end(
    message: Message,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
    question: Question,
):
    if not question:
        await message.answer("""⚠️ <b>Ошибка закрытия</b>

Не удалось найти вопрос в базе""")
        return

    if question.status == "closed":
        await message.reply("""<b>⚠️ Предупреждение</b>

Вопрос уже закрыт""")
        return

    # Останавливаем таймер автозакрытия
    stop_inactivity_timer(question.token)

    # Обновляем статус
    await questions_repo.questions.update_question(
        token=question.token,
        end_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
        status="closed",
    )

    # Уведомляем специалиста
    await message.reply(
        text="🔒 <b>Вопрос закрыт</b>", reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        """⚖️ <b>Оценка вопроса</b>

Оцени, помогли ли тебе решить вопрос

<i>Пожалуйста, удели время оценке. Это важно для статистики</i>""",
        reply_markup=question_finish_employee_kb(question=question),
    )

    # Уведомляем дежурного
    await message.bot.send_message(
        chat_id=question.group_id,
        message_thread_id=question.topic_id,
        text=f"""🔒 <b>Вопрос закрыт</b>

Специалист <b>{format_fullname(user, True, True)}</b> закрыл вопрос

Ответь, мог ли специалист решить вопрос самостоятельно

<i>Если вопрос не решен - ты можешь вернуть его в работу</i>""",
        reply_markup=question_finish_duty_kb(
            question=question,
        ),
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


@user_q.message(ActiveQuestion())
async def active_question(
    message: Message,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
    question: Question,
) -> None:
    if message.message_thread_id:
        return

    if message.voice:
        await message.reply(
            """<b>⚠️ Голосовые сообщения недоступны</b>

Пожалуйста, используй текстовые сообщения для общения"""
        )
        return

    if message.text == "✅️ Закрыть вопрос":
        await active_question_end(
            message=message,
            questions_repo=questions_repo,
            user=user,
            question=question,
        )
        return

    # Перезапускаем таймер бездействия при сообщении от пользователя
    await restart_inactivity_timer(
        question_token=question.token, questions_repo=questions_repo
    )

    # Если реплай - пробуем отправить ответом
    if message.reply_to_message:
        # Находим связь с отвеченным сообщением
        message_pair = await questions_repo.messages_pairs.find_by_user_message(
            user_chat_id=message.chat.id,
            user_message_id=message.reply_to_message.message_id,
        )

        if message_pair:
            # Копируем с ответом если нашли связь
            copied_message = await message.bot.copy_message(
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                reply_to_message_id=message_pair.topic_message_id,
            )
            logger.debug(
                f"[Вопрос] - [Ответ] Найдена связь для ответа: {message.chat.id}:{message.reply_to_message.message_id} -> {message_pair.topic_chat_id}:{message_pair.topic_message_id}"
            )
        else:
            # Не найдено связи, просто копируем
            copied_message = await message.bot.copy_message(
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
            )
    else:
        copied_message = await message.bot.copy_message(
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
        )

    # Сохраняем коннект сообщений
    try:
        await store_message_connection(
            questions_repo=questions_repo,
            user_chat_id=message.chat.id,
            user_message_id=message.message_id,
            topic_chat_id=question.group_id,
            topic_message_id=copied_message.message_id,
            topic_thread_id=question.topic_id,
            question_token=question.token,
            direction="user_to_topic",
        )
    except Exception as e:
        logger.error(f"Failed to store message connection: {e}")

    # Уведомление о премиум эмодзи
    have_premium_emoji, emoji_ids = await check_premium_emoji(message)
    if have_premium_emoji and emoji_ids:
        emoji_sticker_list = await message.bot.get_custom_emoji_stickers(emoji_ids)

        sticker_info = []
        for emoji_sticker in emoji_sticker_list:
            sticker_info.append(f"{emoji_sticker.emoji}")

        stickers_text = "".join(sticker_info)

        emoji_message = await message.reply(f"""<b>💎 Премиум эмодзи</b>

Сообщение содержит премиум эмодзи, собеседник увидит бесплатные аналоги: {stickers_text}

<i>Предупреждение удалится через 30 секунд</i>""")
        await run_delete_timer(
            chat_id=message.chat.id,
            message_ids=[emoji_message.message_id],
            seconds=30,
        )

    logger.info(
        f"[Вопрос] - [Общение] Токен: {question.token} | Специалист: {question.employee_userid} | Сообщение: {message.text if message.text else message.caption}"
    )


@user_q.edited_message(ActiveQuestion())
async def handle_edited_message(
    message: Message,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
    question: Question,
) -> None:
    """Универсальный хендлер для редактируемых сообщений пользователей в активных вопросах"""
    if not question:
        await message.answer("""⚠️ <b>Ошибка</b>

Не удалось найти вопрос в базе""")
        return

    # Проверяем, что вопрос все еще активен
    if question.status == "closed":
        logger.warning(
            f"[Редактирование] Специалист {user.fullname} попытался редактировать сообщение в закрытом вопросе {question.token}"
        )
        return

    # Находим сообщение-пару для редактирования
    pair_to_edit: MessagesPair = await questions_repo.messages_pairs.find_pair_for_edit(
        chat_id=message.chat.id, message_id=message.message_id
    )

    if not pair_to_edit:
        logger.warning(
            f"[Редактирование] Не найдена пара сообщений для редактирования: {message.chat.id}:{message.message_id}"
        )
        return

    edit_timestamp = f"\n\n<i>Сообщение изменено специалистом — {datetime.datetime.now(tz=pytz.timezone('Asia/Yekaterinburg')).strftime('%H:%M %d.%m.%Y')} ПРМ</i>"

    try:
        # Проверяем сообщение на содержание медиа
        if any([
            message.photo,
            message.video,
            message.document,
            message.audio,
            message.animation,
        ]):
            new_media = None

            if message.animation:
                new_media = InputMediaAnimation(media=message.animation.file_id)
            elif message.audio:
                new_media = InputMediaAudio(media=message.audio.file_id)
            elif message.document:
                new_media = InputMediaDocument(media=message.document.file_id)
            elif message.photo:
                new_media = InputMediaPhoto(media=message.photo[-1].file_id)
            elif message.video:
                new_media = InputMediaVideo(media=message.video.file_id)

            if not new_media:
                logger.warning(
                    "[Редактирование] Неподдерживаемый тип медиа для редактирования"
                )
                return

            # Устанавливаем caption с меткой времени редактирования
            if message.caption:
                new_media.caption = message.caption + edit_timestamp
                new_media.caption_entities = message.caption_entities
            else:
                new_media.caption = edit_timestamp.strip()

            # Редактирование медиа в чате со специалистом
            await message.bot.edit_message_media(
                chat_id=pair_to_edit.topic_chat_id,
                message_id=pair_to_edit.topic_message_id,
                media=new_media,
            )

            # Уведомление дежурного об изменении сообщения специалистом
            notify_message = await message.bot.send_message(
                chat_id=pair_to_edit.topic_chat_id,
                message_thread_id=pair_to_edit.topic_thread_id,
                text=f"""<b>♻️ Изменение сообщения</b>

Специалист <b>{short_name(user.fullname)}</b> отредактировал <a href='https://t.me/c/{str(question.group_id)[4:]}/{pair_to_edit.topic_thread_id}/{pair_to_edit.topic_message_id}'>сообщение</a>

<i>Предупреждение удалится через 30 секунд</i>""",
                reply_to_message_id=pair_to_edit.topic_message_id,
            )
            await run_delete_timer(
                chat_id=question.group_id,
                message_ids=[notify_message.message_id],
                seconds=30,
            )

            logger.info(
                f"[Редактирование] Медиа сообщение специалиста отредактировано в вопросе {question.token}"
            )

        elif message.text:
            # Обрабатываем текстовые сообщения
            await message.bot.edit_message_text(
                chat_id=pair_to_edit.topic_chat_id,
                message_id=pair_to_edit.topic_message_id,
                text=message.text + edit_timestamp,
            )

            # Уведомление дежурного об изменении сообщения специалистом
            notify_message = await message.bot.send_message(
                chat_id=pair_to_edit.topic_chat_id,
                message_thread_id=pair_to_edit.topic_thread_id,
                text=f"""<b>♻️ Изменение сообщения</b>

Специалист <b>{short_name(user.fullname)}</b> отредактировал <a href='https://t.me/c/{str(question.group_id)[4:]}/{pair_to_edit.topic_thread_id}/{pair_to_edit.topic_message_id}'>сообщение</a>

<i>Предупреждение удалится через 30 секунд</i>""",
                reply_to_message_id=pair_to_edit.topic_message_id,
            )

            await run_delete_timer(
                chat_id=question.group_id,
                message_ids=[notify_message.message_id],
                seconds=30,
            )

            logger.info(
                f"[Редактирование] Текстовое сообщение специалиста отредактировано в вопросе {question.token}"
            )

        else:
            logger.warning(
                "[Редактирование] Сообщение не содержит ни текста, ни медиа для редактирования"
            )

    except TelegramAPIError as e:
        logger.error(
            f"[Редактирование] Ошибка при редактировании сообщения специалиста в вопросе {question.token}: {e}"
        )
    except Exception as e:
        logger.error(
            f"[Редактирование] Неожиданная ошибка при редактировании сообщения специалиста: {e}"
        )


@user_q.callback_query(QuestionQualitySpecialist.filter())
async def question_quality_employee(
    callback: CallbackQuery,
    callback_data: QuestionQualitySpecialist,
    questions_repo: QuestionsRequestsRepo,
):
    question = await questions_repo.questions.update_question(
        token=callback_data.token, quality_employee=callback_data.answer
    )

    await callback.answer("Оценка успешно выставлена ❤️")

    await callback.message.edit_text(
        """<b>🔒 Вопрос закрыт</b>

<i>Используй меню для взаимодействия с ботом</i>""",
        reply_markup=question_finish_employee_kb(
            question=question,
        ),
    )
