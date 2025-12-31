import logging
from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from stp_database.models.Questions import MessagesPair, Question
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.filters.topic import IsTopicMessage
from tgbot.handlers.group.topic_cmds import end_q_cmd
from tgbot.keyboards.group.main import (
    QuestionAllowReturn,
    QuestionQualityDuty,
    closed_question_duty_kb,
    question_finish_duty_kb,
)
from tgbot.keyboards.user.main import (
    ActivityStatusToggle,
    activity_status_toggle_kb,
    finish_question_kb,
)
from tgbot.middlewares.MessagePairingMiddleware import store_message_connection
from tgbot.misc.helpers import check_premium_emoji, format_fullname, short_name
from tgbot.services.scheduler import (
    restart_inactivity_timer,
    run_delete_timer,
    start_inactivity_timer,
    stop_attention_reminder,
)

topic_router = Router()

logger = logging.getLogger(__name__)


@topic_router.message(IsTopicMessage())
async def handle_q_message(
    message: Message,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=message.chat.id, topic_id=message.message_thread_id
    )
    employee: Employee = await stp_repo.employee.get_users(
        user_id=question.employee_userid
    )

    if message.message_thread_id != question.topic_id:
        return

    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id,
    )

    if message.text == "✅️ Закрыть вопрос":
        await end_q_cmd(
            message=message,
            user=user,
            questions_repo=questions_repo,
            stp_repo=stp_repo,
            question=question,
        )
        return

    if question is not None and question.status != "closed":
        if not question.duty_userid and "".join(
            c for c in employee.division if c.isalpha()
        ) == "".join(c for c in user.division if c.isalpha()):
            duty_topics_today = (
                await questions_repo.questions.get_questions_count_today(
                    duty_userid=user.user_id
                )
            )
            duty_topics_month = (
                await questions_repo.questions.get_questions_count_last_month(
                    duty_userid=str(user.user_id)
                )
            )

            await questions_repo.questions.update_question(
                token=question.token,
                duty_userid=user.user_id,
                status="in_progress",
            )
            stop_attention_reminder(question.token)

            # Запускаем таймер бездействия для нового вопроса
            if question.activity_status_enabled:
                await start_inactivity_timer(
                    question_token=question.token,
                    questions_repo=questions_repo,
                )

            await message.bot.edit_forum_topic(
                chat_id=question.group_id,
                message_thread_id=question.topic_id,
                icon_custom_emoji_id=group_settings.get_setting("emoji_in_progress"),
            )

            try:
                await message.answer(
                    f"""<b>👮‍♂️ Вопрос в работе</b>

На вопрос отвечает <b>{format_fullname(user, True, True)}</b>

<blockquote expandable><b>⚒️ Решено:</b> за день {duty_topics_today} / за месяц {duty_topics_month}</blockquote>""",
                    disable_web_page_preview=True,
                )
            except TelegramBadRequest:
                await message.answer(
                    f"""<b>👮‍♂️ Вопрос в работе</b>

На вопрос отвечает <b>{format_fullname(user, True, True)}</b>

<blockquote expandable><b>⚒️ Решено:</b> за день {duty_topics_today} / за месяц {duty_topics_month}</blockquote>""",
                    disable_web_page_preview=True,
                )

            await message.bot.send_message(
                chat_id=employee.user_id,
                text=f"""<b>👮‍♂️ Вопрос в работе</b>

Дежурный <b>{format_fullname(user, True, True)}</b> взял вопрос в работу""",
                reply_markup=finish_question_kb(),
            )

            copied_message = await message.bot.copy_message(
                from_chat_id=question.group_id,
                message_id=message.message_id,
                chat_id=employee.user_id,
            )

            # Сохраняем коннект сообщений
            try:
                await store_message_connection(
                    questions_repo=questions_repo,
                    user_chat_id=question.employee_userid,
                    user_message_id=copied_message.message_id,
                    topic_chat_id=question.group_id,
                    topic_message_id=message.message_id,
                    topic_thread_id=question.topic_id,
                    question_token=question.token,
                    direction="topic_to_user",
                )
            except Exception as e:
                logger.error(f"Failed to store message connection: {e}")

            logger.info(
                f"[Вопрос] - [В работе] Пользователь {message.from_user.username} ({message.from_user.id}): Вопрос {question.token} взят в работу"
            )
        else:
            if "".join(c for c in employee.division if c.isalpha()) != "".join(
                c for c in user.division if c.isalpha()
            ):
                await message.answer(
                    """<b>⚠️ Внимание</b>

Ты не можешь отвечать на вопросы в этом форуме, форум принадлежит другому направлению

<i>Твое сообщение не отобразится специалисту</i>"""
                )
                return

            if question.duty_userid == user.user_id:
                # Перезапускаем таймер бездействия при сообщении от дежурного
                await restart_inactivity_timer(
                    question_token=question.token,
                    questions_repo=questions_repo,
                )

                # Если реплай - пробуем отправить ответом
                if message.reply_to_message:
                    # Находим связь с отвеченным сообщением
                    message_pair = (
                        await questions_repo.messages_pairs.find_by_topic_message(
                            topic_chat_id=question.group_id,
                            topic_message_id=message.reply_to_message.message_id,
                        )
                    )

                    if message_pair:
                        # Копируем с ответом если нашли связь
                        copied_message = await message.bot.copy_message(
                            from_chat_id=question.group_id,
                            message_id=message.message_id,
                            chat_id=question.employee_userid,
                            reply_to_message_id=message_pair.user_message_id,
                        )
                        logger.info(
                            f"[Вопрос] - [Ответ] Найдена связь для ответа дежурного: {message.chat.id}:{message.reply_to_message.message_id} -> {message_pair.user_chat_id}:{message_pair.user_message_id}"
                        )
                    else:
                        # Не найдено связи, просто копируем
                        copied_message = await message.bot.copy_message(
                            from_chat_id=question.group_id,
                            message_id=message.message_id,
                            chat_id=question.employee_userid,
                        )
                else:
                    copied_message = await message.bot.copy_message(
                        from_chat_id=question.group_id,
                        message_id=message.message_id,
                        chat_id=question.employee_userid,
                    )

                # Сохраняем коннект сообщений
                try:
                    await store_message_connection(
                        questions_repo=questions_repo,
                        user_chat_id=question.employee_userid,
                        user_message_id=copied_message.message_id,
                        topic_chat_id=question.group_id,
                        topic_message_id=message.message_id,
                        topic_thread_id=question.topic_id,
                        question_token=question.token,
                        direction="topic_to_user",
                    )
                except Exception as e:
                    logger.error(f"Failed to store message connection: {e}")

                # Уведомление о премиум эмодзи
                have_premium_emoji, emoji_ids = await check_premium_emoji(message)
                if have_premium_emoji and emoji_ids:
                    emoji_sticker_list = await message.bot.get_custom_emoji_stickers(
                        emoji_ids
                    )

                    sticker_info = []
                    for emoji_sticker in emoji_sticker_list:
                        sticker_info.append(f"{emoji_sticker.emoji}")

                    stickers_text = "".join(sticker_info)

                    emoji_message = await message.reply(f"""<b>💎 Премиум эмодзи</b>

Сообщение содержит премиум эмодзи, собеседник увидит бесплатные аналоги: {stickers_text}

<i>Предупреждение удалится через 30 секунд</i>""")
                    await run_delete_timer(
                        chat_id=question.group_id,
                        message_ids=[emoji_message.message_id],
                        seconds=30,
                    )

                logger.info(
                    f"[Вопрос] - [Общение] Токен: {question.token} | Дежурный: {user.fullname} | Сообщение: {message.text if message.text else message.caption}"
                )
            else:
                await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится специалисту</i>""")
                logger.warning(
                    f"[Вопрос] - [Общение] Токен: {question.token} | Дежурный: {user.fullname} | Сообщение: {message.text if message.text else message.caption}. Чат принадлежит другому старшему"
                )
    elif question.status == "closed":
        await message.reply("""<b>⚠️ Предупреждение</b>

Текущий вопрос уже закрыт!

<i>Твое сообщение не отобразится специалисту</i>""")
        logger.warning(
            f"[Вопрос] - [Общение] Токен: {question.token} | Дежурный: {user.fullname} | Сообщение: {message.text if message.text else message.caption}. Чат уже закрыт"
        )


@topic_router.edited_message(IsTopicMessage())
async def handle_edited_message(
    message: Message, questions_repo: QuestionsRequestsRepo, user: Employee
):
    """Универсальных хендлер для редактируемых сообщений в топиках"""
    question: Question = await questions_repo.questions.get_question(
        group_id=message.chat.id, topic_id=message.message_thread_id
    )
    if not question:
        logger.error(
            f"[Редактирование] Не найдено вопроса для топика: {message.message_thread_id}"
        )
        return

    # Проверяем, что вопрос все еще активен
    if question.status == "closed":
        logger.warning(
            f"[Редактирование] Дежурный {user.fullname} попытался редактировать сообщение в закрытом вопросе {question.token}"
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

    edit_timestamp = f"\n\n<i>Сообщение изменено дежурным — {datetime.now(pytz.timezone('Asia/Yekaterinburg')).strftime('%H:%M %d.%m.%Y')} ПРМ</i>"

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

            if message.caption:
                new_media.caption = message.caption + edit_timestamp
                new_media.caption_entities = message.caption_entities
            else:
                new_media.caption = edit_timestamp.strip()

            # Редактирование медиа в чате со специалистом
            await message.bot.edit_message_media(
                chat_id=pair_to_edit.user_chat_id,
                message_id=pair_to_edit.user_message_id,
                media=new_media,
            )

            # Уведомление специалиста об изменении сообщения дежурным
            await message.bot.send_message(
                chat_id=pair_to_edit.user_chat_id,
                text=f"""<b>♻️ Изменение сообщения</b>

Дежурный <b>{short_name(user.fullname)}</b> отредактировал сообщение""",
                reply_to_message_id=pair_to_edit.user_message_id,
            )

            logger.info(
                f"[Редактирование] Медиа сообщение отредактировано в вопросе {question.token}"
            )

        elif message.text:
            # Обрабатываем сообщения без медиа
            await message.bot.edit_message_text(
                chat_id=pair_to_edit.user_chat_id,
                message_id=pair_to_edit.user_message_id,
                text=message.text + edit_timestamp,
            )

            # Уведомление специалиста об изменении сообщения дежурным
            await message.bot.send_message(
                chat_id=pair_to_edit.user_chat_id,
                text=f"""<b>♻️ Изменение сообщения</b>

Дежурный <b>{short_name(user.fullname)}</b> отредактировал сообщение""",
                reply_to_message_id=pair_to_edit.user_message_id,
            )

            logger.info(
                f"[Редактирование] Текстовое сообщение отредактировано в вопросе {question.token}"
            )

        else:
            logger.warning(
                "[Редактирование] Сообщение не содержит ни текста, ни медиа для редактирования"
            )

    except TelegramAPIError as e:
        logger.error(
            f"[Редактирование] Ошибка при редактировании сообщения в вопросе {question.token}: {e}"
        )
    except Exception as e:
        logger.error(
            f"[Редактирование] Неожиданная ошибка при редактировании сообщения: {e}"
        )


@topic_router.callback_query(QuestionQualityDuty.filter(F.return_question))
async def return_q_duty(
    callback: CallbackQuery, user: Employee, questions_repo: QuestionsRequestsRepo
):
    question: Question = await questions_repo.questions.get_question(
        group_id=callback.message.chat.id, topic_id=callback.message.message_thread_id
    )
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )

    available_to_return_questions = (
        await questions_repo.questions.get_available_to_return_questions()
    )
    active_questions = await questions_repo.questions.get_active_questions()

    if (
        question.status == "closed"
        and question.employee_userid
        not in [u.employee_userid for u in active_questions]
        and question.token in [d.token for d in available_to_return_questions]
        and (question.duty_userid == user.user_id or question.duty_userid is None)
    ):
        await questions_repo.questions.update_question(
            token=question.token, status="in_progress"
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

        await callback.message.answer("""<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы специалисту""")
        await callback.bot.send_message(
            chat_id=question.employee_userid,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

Дежурный <b>{format_fullname(user, True, True)}</b> переоткрыл вопрос:

❓ <b>Изначальный вопрос:</b>
<blockquote expandable>{question.question_text}</blockquote>""",
            reply_markup=finish_question_kb(),
        )
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Вопрос {question.token} переоткрыт старшим"
        )
    elif question.duty_userid != user.user_id:
        await callback.answer("Это не твой чат!", show_alert=True)
        logger.warning(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, вопрос {question.token} принадлежит другому старшему"
        )
    elif question.employee_userid in [d.employee_userid for d in active_questions]:
        await callback.answer(
            "У специалиста есть другой открытый вопрос", show_alert=True
        )
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у специалиста {question.employee_userid} есть другой открытый вопрос"
        )
    elif question.token not in [d.token for d in available_to_return_questions]:
        await callback.answer(
            "Вопрос не переоткрыть. Прошло более 24 часов или возврат заблокирован",
            show_alert=True,
        )
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.token} был закрыт более 24 часов назад или возврат заблокирован"
        )
    elif question.status != "closed":
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.token} не закрыт"
        )

    await callback.answer()


@topic_router.callback_query(IsTopicMessage() and QuestionAllowReturn.filter())
async def change_q_return_status(
    callback: CallbackQuery,
    callback_data: QuestionQualityDuty,
    questions_repo: QuestionsRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=callback.message.chat.id, topic_id=callback.message.message_thread_id
    )
    await questions_repo.questions.update_question(
        token=callback_data.token, allow_return=callback_data.allow_return
    )
    if callback_data.allow_return:
        await callback.answer("🟢 Возврат текущего вопроса был разрешен")
    else:
        await callback.answer("⛔ Возврат текущего вопроса был запрещен")

    await callback.message.edit_reply_markup(
        reply_markup=question_finish_duty_kb(
            question=question,
        )
    )
    await callback.answer()


@topic_router.callback_query(IsTopicMessage() and QuestionQualityDuty.filter())
async def question_quality_duty(
    callback: CallbackQuery,
    callback_data: QuestionQualityDuty,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    question: Question = await questions_repo.questions.get_question(
        group_id=callback.message.chat.id, topic_id=callback.message.message_thread_id
    )
    if question.duty_userid == user.user_id:
        await questions_repo.questions.update_question(
            token=question.token, quality_duty=callback_data.answer
        )
        await callback.answer("Оценка успешно выставлена ❤️")
        if callback_data.answer:
            await callback.message.edit_text(
                f"""<b>🔒 Вопрос закрыт</b>

👮‍♂️ Дежурный <b>{format_fullname(user, True, True)}</b> поставил оценку:
👍 Специалист <b>не мог решить вопрос самостоятельно</b>""",
                reply_markup=closed_question_duty_kb(
                    token=callback_data.token, allow_return=question.allow_return
                ),
            )
        else:
            await callback.message.edit_text(
                f"""<b>🔒 Вопрос закрыт</b>

👮‍♂️ Дежурный <b>{format_fullname(user, True, True)}</b> поставил оценку:
👎 Специалист <b>мог решить вопрос самостоятельно</b>""",
                reply_markup=closed_question_duty_kb(
                    token=callback_data.token, allow_return=question.allow_return
                ),
            )

        logger.info(
            f"[Вопрос] - [Оценка] Пользователь {callback.from_user.username} ({callback.from_user.id}): Выставлена оценка {callback_data.answer} вопросу {question.token} от старшего"
        )
    else:
        await callback.answer("Это не твой чат!", show_alert=True)
        logger.warning(
            f"[Вопрос] - [Оценка] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка выставить оценку {callback_data.answer} вопросу {question.token}. Вопрос принадлежит другому старшему"
        )
    await callback.answer()


@topic_router.callback_query(ActivityStatusToggle.filter())
async def toggle_activity_status(
    callback: CallbackQuery,
    callback_data: ActivityStatusToggle,
    questions_repo: QuestionsRequestsRepo,
):
    """Обработчик переключения статуса активности для топика"""
    question: Question = await questions_repo.questions.get_question(
        group_id=callback.message.chat.id, topic_id=callback.message.message_thread_id
    )

    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=callback.chat.id,
    )

    try:
        if not question:
            await callback.answer("❌ Вопрос не найден", show_alert=True)
            return
        elif question.status not in ["open", "in_progress"]:
            await callback.answer("Вопрос уже закрыт")
            return

        # Определяем новое значение статуса активности
        if callback_data.action == "enable":
            new_status = True
            action_text = "включен"

        else:  # disable
            new_status = False
            action_text = "отключен"
            from tgbot.services.scheduler import stop_inactivity_timer

            stop_inactivity_timer(question.token)

        # Обновляем статус в базе данных
        await questions_repo.questions.update_question(
            token=callback_data.token, activity_status_enabled=new_status
        )

        # Теперь запускаем таймер если включили активность
        if new_status and question.status in [
            "open",
            "in_progress",
        ]:
            await start_inactivity_timer(
                question_token=question.token,
                questions_repo=questions_repo,
            )

        # Обновляем клавиатуру
        await callback.message.edit_reply_markup(
            reply_markup=activity_status_toggle_kb(
                token=callback_data.token,
                clever_link=question.clever_link if question.clever_link else None,
                current_status=new_status,
                global_status=group_settings.get_setting("activity_status"),
            )
        )

        # Показываем уведомление пользователю
        if new_status:
            await callback.answer(
                f"🟢 Статус активности {action_text} для данного топика"
            )
        else:
            await callback.answer(
                f"🟠 Статус активности {action_text} для данного топика"
            )

        # Отправляем уведомление в топик (автоудаление через 10 секунд)
        if new_status:
            topic_message_text = "🟢 <b>Автозакрытие включено</b>\n\nТопик будет автоматически закрыт при отсутствии активности\n\n<i>Сообщение удалится через 10 секунд</i>"
        else:
            topic_message_text = "🟠 <b>Автозакрытие отключено</b>\n\nТопик не будет закрываться автоматически\n\n<i>Сообщение удалится через 10 секунд</i>"

        topic_msg = await callback.bot.send_message(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            text=topic_message_text,
        )

        # Отправляем уведомление пользователю (автоудаление через 10 секунд)
        if new_status:
            user_message_text = "🟢 <b>Автозакрытие включено</b>\n\nДежурный включил автоматические закрытие вопроса при отсутствии активности\n\n<i>Сообщение удалится через 10 секунд</i>"
        else:
            user_message_text = "🟠 <b>Автозакрытие отключено</b>\n\nДежурный выключил автоматические закрытие вопроса при отсутствии активности\n\n<i>Сообщение удалится через 10 секунд</i>"

        user_msg = await callback.bot.send_message(
            chat_id=question.employee_userid,
            text=user_message_text,
        )

        # Запускаем таймеры удаления для обоих сообщений
        await run_delete_timer(
            chat_id=question.group_id,
            message_ids=[topic_msg.message_id],
            seconds=10,
        )

        await run_delete_timer(
            chat_id=question.employee_userid,
            message_ids=[user_msg.message_id],
            seconds=10,
        )

        logger.info(
            f"[Активность] Дежурный {callback.from_user.username} ({callback.from_user.id}): "
            f"Статус активности {action_text} для вопроса {question.token}"
        )

    except Exception as e:
        logger.error(f"[Активность] Ошибка при переключении статуса активности: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
    await callback.answer()
