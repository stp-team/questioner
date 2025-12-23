import datetime
import logging

import pytz
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from stp_database.models.STP import Employee
from stp_database.repo.Questions.requests import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.keyboards.user.main import activity_status_toggle_kb, cancel_question_kb
from tgbot.misc.helpers import extract_clever_link, get_target_forum, short_name
from tgbot.services.scheduler import start_attention_reminder


async def on_message_input(
    message: Message, _widget, dialog_manager: DialogManager, **_kwargs
):
    """Сохранение сообщения пользователя для последующего копирования."""
    dialog_manager.dialog_data["user_message"] = {
        "text": message.text or message.caption or "",
        "message_id": message.message_id,
        "chat_id": message.chat.id,
    }
    if message.photo:
        dialog_manager.dialog_data["user_message"]["photo"] = message.photo[-1].file_id
    elif message.document:
        dialog_manager.dialog_data["user_message"]["document"] = (
            message.document.file_id
        )
    await dialog_manager.next()


async def check_link(
    message: Message, _widget, dialog_manager: DialogManager, text: str, **_kwargs
):
    """Валидация ссылки на регламент."""
    if not text.startswith("http"):
        text = "https://" + text

    if "clever.ertelecom.ru" not in text:
        return "❌ Ссылка должна содержать 'clever.ertelecom.ru'"

    # Проверяем на запрещенные ссылки
    extracted_link = extract_clever_link(text)
    if extracted_link:
        forbidden_links = [
            "https://clever.ertelecom.ru/content/space/4/wiki/1808",
            "https://clever.ertelecom.ru/content/space/4/wiki/1808/",
            "https://clever.ertelecom.ru/content/space/4/wiki/1808/page/0",
            "https://clever.ertelecom.ru/content/space/4/wiki/1808/page/0/",
            "https://clever.ertelecom.ru/content/space/4/wiki/1808/page/1",
            "https://clever.ertelecom.ru/content/space/4/wiki/1808/page/1/",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259/",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259/page/0",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259/page/0/",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259/page/1",
            "https://clever.ertelecom.ru/content/space/4/wiki/10259/page/1/",
            "https://clever.ertelecom.ru/content/space/4",
            "https://clever.ertelecom.ru/content/space/4/",
        ]
        if extracted_link in forbidden_links:
            return "❌ Ссылка содержит запрещенную страницу. Отправь корректную ссылку на регламент"

    dialog_manager.dialog_data["regulation_link"] = text
    await dialog_manager.next()


async def on_confirm(
    callback: CallbackQuery, _button, dialog_manager: DialogManager, **_kwargs
):
    """Обработка подтверждения отправки вопроса."""
    # Получаем данные из контекста
    user: Employee = dialog_manager.middleware_data["user"]
    questions_repo: QuestionsRequestsRepo = dialog_manager.middleware_data["questions_repo"]
    main_repo: MainRequestsRepo = dialog_manager.middleware_data["main_repo"]

    # Проверяем активные вопросы
    active_questions = await questions_repo.questions.get_active_questions()
    if user.user_id in [q.employee_userid for q in active_questions]:
        await callback.answer("У тебя уже есть активный вопрос")
        await dialog_manager.done()
        return

    # Получаем сохраненные данные диалога
    user_message = dialog_manager.dialog_data.get("user_message", {})
    regulation_link = dialog_manager.dialog_data.get("regulation_link")
    question_text = user_message.get("text", "")

    if not question_text or question_text.strip() == "":
        await callback.answer("❌ Вопрос не может быть пустым")
        await dialog_manager.done()
        return

    # Получаем статистику пользователя
    employee_topics_today = await questions_repo.questions.get_questions_count_today(
        employee_userid=user.user_id
    )
    employee_topics_month = (
        await questions_repo.questions.get_questions_count_last_month(
            employee_userid=user.fullname
        )
    )

    # Получаем настройки группы
    target_forum_id = await get_target_forum(user)
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=target_forum_id
    )

    try:
        # Создаем тему форума
        new_topic = await callback.bot.create_forum_topic(
            chat_id=target_forum_id,
            name=f"{user.division} | {short_name(user.fullname)}"
            if group_settings.get_setting("show_division")
            else short_name(user.fullname),
            icon_custom_emoji_id=group_settings.get_setting("emoji_open"),
        )

        # Создаем новый вопрос в БД
        new_question = await questions_repo.questions.add_question(
            group_id=target_forum_id,
            topic_id=new_topic.message_thread_id,
            employee_userid=callback.from_user.id,
            start_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
            question_text=question_text,
            clever_link=regulation_link,
            activity_status_enabled=group_settings.get_setting("activity_status"),
        )

        # Отправляем сообщение об успехе
        await callback.message.edit_text(
            """<b>✅ Успешно</b>

Вопрос передан на рассмотрение, в скором времени тебе ответят""",
            reply_markup=cancel_question_kb(token=new_question.token),
        )

        # Формируем информацию о пользователе
        if user.username:
            user_fullname = f"<a href='t.me/{user.username}'>{short_name(user.fullname)}</a>"
        else:
            user_fullname = short_name(user.fullname)

        head = await main_repo.employee.get_users(fullname=user.head)
        if head and head.username:
            head_fullname = f"<a href='t.me/{head.username}'>{short_name(head.fullname)}</a>"
        else:
            head_fullname = short_name(user.head)

        # Отправляем информационное сообщение в тему
        topic_text = f"""Вопрос задает <b>{user_fullname}</b>

<blockquote expandable><b>👔 Должность:</b> {user.position}
<b>👑 Руководитель:</b> {head_fullname}

<b>❓ Вопросов:</b> за день {employee_topics_today} / за месяц {employee_topics_month}</blockquote>"""

        topic_info_msg = await callback.bot.send_message(
            chat_id=new_question.group_id,
            message_thread_id=new_topic.message_thread_id,
            text=topic_text,
            disable_web_page_preview=True,
            reply_markup=activity_status_toggle_kb(
                token=new_question.token,
                clever_link=regulation_link if regulation_link else None,
                current_status=new_question.activity_status_enabled,
                global_status=group_settings.get_setting("activity_status"),
            ),
        )

        # Копируем сообщение пользователя в тему
        await callback.bot.copy_message(
            chat_id=new_question.group_id,
            message_thread_id=new_topic.message_thread_id,
            from_chat_id=user_message.get("chat_id"),
            message_id=user_message.get("message_id"),
        )

        # Закрепляем информационное сообщение
        await callback.bot.pin_chat_message(
            chat_id=new_question.group_id,
            message_id=topic_info_msg.message_id,
            disable_notification=True,
        )

        # Запускаем напоминание
        await start_attention_reminder(new_question.token, questions_repo)

        logging.info(
            f"[Dialog] {callback.from_user.username} ({callback.from_user.id}): Создан новый вопрос {new_question.token}"
        )

        await callback.answer("Вопрос успешно создан!")
        await dialog_manager.done()

    except Exception as e:
        logging.error(f"Ошибка при создании вопроса: {e}")
        await callback.answer("❌ Произошла ошибка при создании вопроса")
        await dialog_manager.done()
