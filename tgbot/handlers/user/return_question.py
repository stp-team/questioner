import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from stp_database import Employee, MainRequestsRepo, Question, QuestionsRequestsRepo

from tgbot.keyboards.group.main import reopened_question_kb
from tgbot.keyboards.user.main import (
    MainMenu,
    QuestionQualitySpecialist,
    ReturnQuestion,
    back_kb,
    finish_question_kb,
    question_confirm_kb,
    questions_list_kb,
    user_kb,
)
from tgbot.misc.helpers import short_name
from tgbot.services.logger import setup_logging

employee_return_q_router = Router()
employee_return_q_router.message.filter(F.chat.type == "private")
employee_return_q_router.callback_query.filter(F.message.chat.type == "private")

setup_logging()
logger = logging.getLogger(__name__)


@employee_return_q_router.callback_query(
    QuestionQualitySpecialist.filter(F.return_question)
)
async def return_finished_q(
    callback: CallbackQuery,
    callback_data: QuestionQualitySpecialist,
    state: FSMContext,
    questions_repo: QuestionsRequestsRepo,
    main_repo: MainRequestsRepo,
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
        duty: Employee = await main_repo.employee.get_users(
            user_id=question.duty_userid
        )
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


@employee_return_q_router.callback_query(MainMenu.filter(F.menu == "return"))
async def q_list(
    callback: CallbackQuery,
    state: FSMContext,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Меню "🔄 Возврат вопроса". Отображает последние 5 закрытых вопросов за последние 24 часа для возврата в работу со стороны специалиста."""
    questions: Sequence[
        Question
    ] = await questions_repo.questions.get_last_questions_by_chat_id(
        employee_chat_id=callback.from_user.id, limit=5
    )

    state_data = await state.get_data()
    if not questions:
        await callback.message.edit_text(
            """<b>🔄 Возврат вопроса</b>

📝 У тебя нет закрытых вопросов за последние 24 часа""",
            reply_markup=back_kb(),
        )
        logging.warning(
            f"{'[Админ]' if state_data.get('role') or user.role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто меню возврата чата, доступных вопросов нет"
        )
        return

    await callback.message.edit_text(
        """<b>🔄 Возврат вопроса</b>

📋 Выбери вопрос из списка доступных

<i>Отображаются вопросы, закрытые за последние 24 часа</i>""",
        reply_markup=questions_list_kb(questions),
    )
    logging.info(
        f"{'[Админ]' if state_data.get('role') or user.role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто меню возврата чата"
    )
    await callback.answer()


@employee_return_q_router.callback_query(ReturnQuestion.filter(F.action == "show"))
async def q_info(
    callback: CallbackQuery,
    callback_data: ReturnQuestion,
    state: FSMContext,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    main_repo: MainRequestsRepo,
):
    """Меню описания выбранного специалистом вопроса для возврата в работу"""
    question: Question = await questions_repo.questions.get_question(
        token=callback_data.token
    )

    if not question:
        await callback.message.edit_text("❌ Вопрос не найден", reply_markup=user_kb())
        return

    if question.duty_userid:
        duty: Employee = await main_repo.employee.get_users(
            user_id=question.duty_userid
        )
    else:
        duty = None

    state_data = await state.get_data()
    start_date_str = question.start_time.strftime("%d.%m.%Y %H:%M")
    end_date_str = (
        question.end_time.strftime("%d.%m.%Y %H:%M")
        if question.end_time
        else "Не указано"
    )
    question_text = (
        question.question_text[:200] + "..."
        if len(question.question_text) > 200
        else question.question_text
    )

    # Добавляем инфо только если у вопроса есть закрепленный дежурный
    duty_info = ""
    if duty:
        duty_info = f"\n<b>👮‍♂️ Дежурный:</b> {duty.fullname}{'\n<span class="tg-spoiler">@' + duty.username + '</span>' if duty.username != 'Не указан' or 'Скрыто/не определено' else ''}"

    await callback.message.edit_text(
        f"""<b>🔄 Возврат вопроса</b>

❓ <b>Вопрос:</b>
<blockquote expandable>{question_text}</blockquote>

🗃️ <b>Регламент:</b> {"<a href='" + question.clever_link + "'>тык</a>" if question.clever_link else "Не указан"} {duty_info}
🚀 <b>Дата создания:</b> {start_date_str}
🔒 <b>Дата закрытия:</b> {end_date_str}

Хочешь вернуть этот вопрос?""",
        reply_markup=question_confirm_kb(question.token),
        disable_web_page_preview=True,
    )
    logging.info(
        f"{'[Админ]' if state_data.get('role') or user.role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто описание вопроса {question.token} для возврата"
    )
    await callback.answer()


@employee_return_q_router.callback_query(ReturnQuestion.filter(F.action == "confirm"))
async def return_q_confirm(
    callback: CallbackQuery,
    callback_data: ReturnQuestion,
    state: FSMContext,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    main_repo: MainRequestsRepo,
):
    """Возврат выбранного специалистом вопроса в работу"""
    await state.clear()

    question: Question = await questions_repo.questions.get_question(
        token=callback_data.token
    )

    if not question:
        await callback.message.edit_text("❌ Вопрос не найден", reply_markup=user_kb())
        return

    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=question.group_id,
    )

    active_questions = await questions_repo.questions.get_active_questions()

    if (
        question.status == "closed"
        and user.user_id not in [d.employee_userid for d in active_questions]
        and question.allow_return
    ):
        # Get duty user only if topic_duty_fullname exists
        duty = None
        if question.duty_userid:
            duty: Employee = await main_repo.employee.get_users(
                user_id=question.duty_userid
            )

        # 1. Обновляем статус вопроса на "open"
        await questions_repo.questions.update_question(
            token=question.token,
            status="open",
        )

        # 2. Обновляем название и иконку темы
        await callback.bot.edit_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            name=f"{user.division} | {short_name(user.fullname)}"
            if group_settings.get_setting("show_division")
            else short_name(user.fullname),
            icon_custom_emoji_id=group_settings.get_setting("emoji_in_progress"),
        )

        # 3. Переоткрываем тему
        await callback.bot.reopen_forum_topic(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
        )

        # 4. Отправляем подтверждающее сообщение специалисту
        await callback.message.answer(
            """<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""",
            reply_markup=finish_question_kb(),
        )

        # 5. Build duty info only if duty exists
        duty_info = ""
        if duty:
            duty_info = f"\n<b>👮‍♂️ Дежурный:</b> {duty.fullname}{'\n<span class="tg-spoiler">@' + duty.username + '</span>' if duty.username != 'Не указан' or 'Скрыто/не определено' else ''}"

        # 6. Отправляем уведомление дежурному в тему
        await callback.bot.send_message(
            chat_id=question.group_id,
            message_thread_id=question.topic_id,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

Специалист <b>{short_name(user.fullname)}</b> переоткрыл вопрос из истории вопросов
{duty_info}

<b>❓ Изначальный вопрос:</b>
<blockquote expandable><i>{question.question_text}</i></blockquote>""",
            reply_markup=reopened_question_kb(),
            disable_web_page_preview=True,
        )
    elif user.user_id in [d.employee_userid for d in active_questions]:
        # Проверка на наличие открытых вопросов у специалиста
        await callback.answer("У тебя есть другой открытый вопрос", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у специалиста {question.employee_userid} есть другой открытый вопрос"
        )
    elif question.status != "closed":
        # Проверка на закрытость вопроса
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, вопрос {question.token} не закрыт"
        )
    elif not question.allow_return:
        # Проверка на доступность возврата вопроса
        await callback.answer("Возврат вопроса заблокирован", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, вопрос {question.token} заблокирован для возврата"
        )
    else:
        await callback.answer("Не удалось переоткрыть вопрос", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия вопроса {question.token}"
        )
    await callback.answer()
