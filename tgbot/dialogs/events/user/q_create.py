import datetime
import logging
from typing import Any

import pytz
import validators
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from stp_database.models.STP import Employee
from stp_database.repo.Questions.requests import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.dialogs.states.user.main import QuestionSG
from tgbot.keyboards.user.main import activity_status_toggle_kb, cancel_question_kb
from tgbot.misc.helpers import (
    extract_clever_link,
    format_fullname,
    get_target_forum,
    short_name,
)
from tgbot.services.scheduler import start_attention_reminder


async def start_question_dialog(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(QuestionSG.question_text)


async def on_message_input(
    message: Message, _widget, dialog_manager: DialogManager, **_kwargs
):
    """Сохранение сообщения пользователя для последующего копирования."""
    message_text = message.text or message.caption or ""

    dialog_manager.dialog_data["user_message"] = {
        "text": message_text,
        "message_id": message.message_id,
        "chat_id": message.chat.id,
    }
    if message.photo:
        dialog_manager.dialog_data["user_message"]["photo"] = message.photo[-1].file_id
    elif message.document:
        dialog_manager.dialog_data["user_message"]["document"] = (
            message.document.file_id
        )

    # Получаем пользователя и настройки группы
    user: Employee = dialog_manager.middleware_data["user"]
    questions_repo: QuestionsRequestsRepo = dialog_manager.middleware_data[
        "questions_repo"
    ]

    # Получаем настройки группы для проверки ask_clever_link
    target_forum_id = await get_target_forum(user)
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=target_forum_id
    )

    # Если настройка ask_clever_link выключена, создаем вопрос сразу
    if not group_settings.get_setting("ask_clever_link"):
        await create_question(message, dialog_manager)
        return

    # Проверяем, есть ли ссылка на Клевер в тексте сообщения
    extracted_link = extract_clever_link(message_text)

    if extracted_link:
        try:
            # Валидируем найденную ссылку
            validated_link = validate_link(extracted_link)

            # Сохраняем ссылку в данные диалога
            dialog_manager.dialog_data["link"] = validated_link

            # Создаем вопрос сразу, пропуская этап ввода ссылки
            await create_question(message, dialog_manager)
        except ValueError:
            # Если ссылка невалидна, переходим к этапу ввода ссылки
            await dialog_manager.next()
    else:
        await dialog_manager.next()


async def check_link(
    _message: Message, _widget, dialog_manager: DialogManager, text: str, **_kwargs
):
    """Валидация ссылки на регламент."""
    if not text.startswith("http"):
        text = "https://" + text

    if "clever.ertelecom.ru" not in text:
        return "Ссылка должна вести на <a href='clever.ertelecom.ru'>Клевер</a>"

    if not validators.url(text):
        return "Некорректная ссылка. Проверь правильность ввода"

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

    dialog_manager.dialog_data["link"] = text
    await dialog_manager.next()
    return None


def validate_link(text: str) -> str:
    """Валидация ссылки на регламент для TextInput.

    Args:
        text: Введенный текст ссылки

    Returns:
        str: Валидированная ссылка

    Raises:
        ValueError: Если ссылка невалидна
    """
    if not text.startswith("http"):
        text = "https://" + text

    if "clever.ertelecom.ru" not in text:
        raise ValueError("Ссылка должна вести на Клевер")

    if not validators.url(text):
        raise ValueError("Некорректная ссылка. Проверь правильность ввода")

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
            raise ValueError(
                "❌ Ссылка содержит запрещенную страницу. Отправь корректную ссылку на регламент"
            )

    return text


async def link_error(
    message: Message, _widget, _dialog_manager: DialogManager, error_: ValueError
):
    """Обработка ошибок валидации ссылки."""
    await message.answer(f"❌ {str(error_)}")


async def on_link_success(
    message: Message, _widget, dialog_manager: DialogManager, text: str, **_kwargs
):
    """Обработка успешного ввода ссылки - создает вопрос."""
    dialog_manager.dialog_data["link"] = text
    await create_question(message, dialog_manager)


async def create_question(
    event: CallbackQuery | Message, dialog_manager: DialogManager
):
    """Создание вопроса.

    Args:
        event: Событие (CallbackQuery или Message)
        dialog_manager: Менеджер диалога
    """
    # Получаем данные из контекста
    user: Employee = dialog_manager.middleware_data["user"]
    questions_repo: QuestionsRequestsRepo = dialog_manager.middleware_data[
        "questions_repo"
    ]
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]

    head = await stp_repo.employee.get_users(fullname=user.head)

    # Проверяем активные вопросы
    active_questions = await questions_repo.questions.get_active_questions()
    if user.user_id in [q.employee_userid for q in active_questions]:
        answer_text = "У тебя уже есть активный вопрос"
        if isinstance(event, CallbackQuery):
            await event.answer(answer_text)
        else:
            await event.answer(answer_text)
        await dialog_manager.done()
        return

    # Получаем сохраненные данные диалога
    user_message = dialog_manager.dialog_data.get("user_message", {})
    regulation_link = dialog_manager.dialog_data.get("link")
    question_text = user_message.get("text", "")

    if not question_text or question_text.strip() == "":
        answer_text = "❌ Вопрос не может быть пустым"
        if isinstance(event, CallbackQuery):
            await event.answer(answer_text)
        else:
            await event.answer(answer_text)
        await dialog_manager.done()
        return

    # Получаем статистику пользователя
    employee_topics_today = await questions_repo.questions.get_questions_count_today(
        employee_userid=user.user_id
    )
    employee_topics_month = (
        await questions_repo.questions.get_questions_count_last_month(
            employee_userid=user.user_id
        )
    )

    # Получаем настройки группы
    target_forum_id = await get_target_forum(user)
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=target_forum_id
    )

    try:
        # Создаем тему форума
        new_topic = await event.bot.create_forum_topic(
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
            employee_userid=event.from_user.id,
            start_time=datetime.datetime.now(tz=pytz.timezone("Asia/Yekaterinburg")),
            question_text=question_text,
            clever_link=regulation_link,
            activity_status_enabled=group_settings.get_setting("activity_status"),
        )

        # Отправляем сообщение об успехе
        if isinstance(event, CallbackQuery):
            await event.message.answer(
                """<b>✅ Успешно</b>

Вопрос передан на рассмотрение, в скором времени тебе ответят""",
                reply_markup=cancel_question_kb(token=new_question.token),
            )
        else:
            await event.answer(
                """<b>✅ Успешно</b>

Вопрос передан на рассмотрение, в скором времени тебе ответят""",
                reply_markup=cancel_question_kb(token=new_question.token),
            )

        # Отправляем информационное сообщение в тему
        topic_text = f"""Вопрос задает <b>{format_fullname(user, True, True)}</b>

<blockquote expandable><b>👔 Должность:</b> {user.position}
<b>👑 Руководитель:</b> <b>{format_fullname(head, True, True)}</b>

<b>❓ Вопросов:</b> за день {employee_topics_today} / за месяц {employee_topics_month}</blockquote>

<i>Токен вопроса: <code>{new_question.token}</code></i>"""

        topic_info_msg = await event.bot.send_message(
            chat_id=new_question.group_id,
            message_thread_id=new_topic.message_thread_id,
            text=topic_text,
            disable_web_page_preview=True,
            reply_markup=activity_status_toggle_kb(
                token=new_question.token,
                clever_link=regulation_link
                if regulation_link and validators.url(regulation_link)
                else None,
                current_status=new_question.activity_status_enabled,
                global_status=group_settings.get_setting("activity_status"),
            ),
        )

        # Копируем сообщение пользователя в тему
        await event.bot.copy_message(
            chat_id=new_question.group_id,
            message_thread_id=new_topic.message_thread_id,
            from_chat_id=user_message.get("chat_id"),
            message_id=user_message.get("message_id"),
        )

        # Закрепляем информационное сообщение
        await event.bot.pin_chat_message(
            chat_id=new_question.group_id,
            message_id=topic_info_msg.message_id,
            disable_notification=True,
        )

        # Запускаем напоминание
        await start_attention_reminder(new_question.token, questions_repo)

        logging.debug(
            f"[Dialog] {event.from_user.username} ({event.from_user.id}): Создан новый вопрос {new_question.token}"
        )

        await dialog_manager.done(show_mode=ShowMode.NO_UPDATE)

        if isinstance(event, CallbackQuery):
            if event.message:
                await event.message.delete()
            await event.answer(
                "Вопрос передан на рассмотрение, в скором времени тебе ответят"
            )

    except Exception as e:
        logging.error(f"Ошибка при создании вопроса: {e}")
        answer_text = "❌ Произошла ошибка при создании вопроса"
        if isinstance(event, CallbackQuery):
            await event.answer(answer_text)
        else:
            await event.answer(answer_text)
        await dialog_manager.done()
