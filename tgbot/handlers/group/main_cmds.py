import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from stp_database.models.STP import Employee
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.filters.topic import IsMainTopicMessageWithCommand
from tgbot.keyboards.group.settings import (
    SettingsEmoji,
    SettingsEmojiPage,
    settings_emoji,
)
from tgbot.services.logger import setup_logging

main_topic_cmds_router = Router()

setup_logging()
logger = logging.getLogger(__name__)


@main_topic_cmds_router.message(Command("question"), IsMainTopicMessageWithCommand())
async def question_info(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
):
    """Получение информации о вопросе."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к информации о вопросах есть только у руководителей"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /question [токен вопроса]")
        return

    token = command.args.split(maxsplit=1)[0].lower()

    # Получаем текущие настройки
    question = await questions_repo.questions.get_question(
        token=token, group_id=message.chat.id
    )

    if question:
        duty = await stp_repo.employee.get_users(user_id=question.duty_userid)
        employee = await stp_repo.employee.get_users(user_id=question.employee_userid)

        response = f"""<b>Информация о вопросе</b>

<code>{token}</code>

Дежурный: <a href='t.me/{duty.username}'>{duty.fullname}</a>
Вопрошающий: <a href='t.me/{employee.username}'>{employee.fullname}</a>

Текст вопроса:
<blockquote expandable>{question.question_text}</blockquote>

Возврат: {"Разрешен" if question.allow_return else "Запрещен"}

<blockquote expandable>ID группы: {question.group_id}
ID темы: {question.topic_id}</blockquote>"""

    else:
        response = f"Не удалось найти вопрос с токеном {token}"

    await message.reply(response, disable_web_page_preview=True)


@main_topic_cmds_router.message(IsMainTopicMessageWithCommand("link"))
async def link_cmd(message: Message):
    group_link = await message.bot.export_chat_invite_link(chat_id=message.chat.id)
    await message.reply(
        f"Пригласительная ссылка на этот чат:\n<code>{group_link}</code>"
    )


@main_topic_cmds_router.message(IsMainTopicMessageWithCommand("settings"))
async def settings_cmd(message: Message, questions_repo: QuestionsRequestsRepo):
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id,
    )

    custom_emojis = await message.bot.get_forum_topic_icon_stickers()

    # Create a lookup dictionary for faster searching
    emoji_lookup = {emoji.custom_emoji_id: emoji for emoji in custom_emojis}

    # Находим идентификаторы эмодзи
    emoji_ids = {
        "open": group_settings.get_setting("emoji_open"),
        "in_work": group_settings.get_setting("emoji_in_progress"),
        "closed": group_settings.get_setting("emoji_closed"),
        "cancelled": group_settings.get_setting("emoji_fired"),
    }

    # Форматирование эмодзи для ТГ
    def format_emoji(emoji_id, fallback):
        if emoji_id and str(emoji_id) in emoji_lookup:
            emoji = emoji_lookup[str(emoji_id)]
            return (
                f'<tg-emoji emoji-id="{emoji.custom_emoji_id}">{emoji.emoji}</tg-emoji>'
            )
        else:
            return fallback

    await message.reply(
        f"""<b>⚙️ Настройки чата:</b> <code>{group_settings.group_name}</code>

<b>🧩 Функции:</b>
- Запрос регламента - {"✅" if group_settings.get_setting("ask_clever_link") else "❌"} (/clever)
- Отображение направления - {"✅" if group_settings.get_setting("show_division") else "❌"} (/division)
- Закрытие по бездействию - {"✅" if group_settings.get_setting("activity_status") else "❌"} (/activity)

<b>⏳ Таймеры:</b>
- Предупреждение о бездействии: {group_settings.get_setting("activity_warn_minutes")} минут (/warn)
- Закрытие по бездействию: {group_settings.get_setting("activity_close_minutes")} минут (/close)

<b>💡 Статусы</b>
- Открытый вопрос: {format_emoji(emoji_ids["open"], "неизвестно")} (/emoji_open)
- В работе: {format_emoji(emoji_ids["in_work"], "неизвестно")} (/emoji_in_progress)
- Закрытый вопрос: {format_emoji(emoji_ids["closed"], "неизвестно")} (/emoji_closed)
- Отмененный вопрос: {format_emoji(emoji_ids["cancelled"], "неизвестно")} (/emoji_fired)

<i>Изменять настройки могут только РГ и администраторы</i>""",
        parse_mode="HTML",
    )


@main_topic_cmds_router.message(Command("clever"), IsMainTopicMessageWithCommand())
async def ask_clever_link_change(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Управление статусом запроса регламента для форумов."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /clever [on или off]")
        return

    action = command.args.split(maxsplit=1)[0].lower()
    if action not in ("on", "off"):
        await message.reply("Пример команды: /clever [on или off]")
        return

    # Получаем текущие настройки
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id
    )

    current_state = group_settings.get_setting("ask_clever_link")
    target_state = action == "on"
    user_name = user.fullname

    # Определяем ответ в зависимости от текущего состояния настройки и нового состояния
    if current_state == target_state:
        status = "включен" if current_state else "выключен"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Запрос регламента <b>уже {status}</b>"
        )
    else:
        # Обновление настроек
        await questions_repo.settings.update_setting(
            group_id=message.chat.id, key="ask_clever_link", value=target_state
        )
        action_text = "включил" if target_state else "выключил"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Пользователь <b>{user_name}</b> {action_text} запрос регламента"
        )

    await message.reply(response)


@main_topic_cmds_router.message(Command("division"), IsMainTopicMessageWithCommand())
async def show_division_change(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Управление статусом отображения направления специалиста для форумов."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /division [on или off]")
        return

    action = command.args.split(maxsplit=1)[0].lower()
    if action not in ("on", "off"):
        await message.reply("Пример команды: /division [on или off]")
        return

    # Получаем текущие настройки
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id
    )

    current_state = group_settings.get_setting("show_division")
    target_state = action == "on"
    user_name = user.fullname

    # Определяем ответ в зависимости от текущего состояния настройки и нового состояния
    if current_state == target_state:
        status = "включено" if current_state else "выключено"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Отображения направления специалистов <b>уже {status}</b>"
        )
    else:
        # Обновление настроек
        await questions_repo.settings.update_setting(
            group_id=message.chat.id, key="show_division", value=target_state
        )
        action_text = "включил" if target_state else "выключил"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Пользователь <b>{user_name}</b> {action_text} отображение направления специалистов"
        )

    await message.reply(response)


@main_topic_cmds_router.message(Command("activity"), IsMainTopicMessageWithCommand())
async def activity_change(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Управление статусом закрытия по бездействию."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /activity [on или off]")
        return

    action = command.args.split(maxsplit=1)[0].lower()
    if action not in ("on", "off"):
        await message.reply("Пример команды: /activity [on или off]")
        return

    # Получаем текущие настройки
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id
    )

    current_state = group_settings.get_setting("activity_status")
    target_state = action == "on"
    user_name = user.fullname

    # Определяем ответ в зависимости от текущего состояния настройки и нового состояния
    if current_state == target_state:
        status = "включено" if current_state else "выключено"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Закрытие по бездействию <b>уже {status}</b>"
        )
    else:
        # Обновление настроек
        await questions_repo.settings.update_setting(
            group_id=message.chat.id, key="activity_status", value=target_state
        )
        action_text = "включил" if target_state else "выключил"
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Пользователь <b>{user_name}</b> {action_text} закрытие по бездействию"
        )

    await message.reply(response)


@main_topic_cmds_router.message(Command("warn"), IsMainTopicMessageWithCommand())
async def timer_warn_change(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Управление временем предупреждения о закрытии по бездействию."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /warn [время в минутах]")
        return

    new_timer = command.args.split(maxsplit=1)[0]
    if type(int(new_timer)) is not int:
        await message.reply("Пример команды: /warn [время в минутах]")
        return

    # Получаем текущие настройки
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id
    )

    current_state = int(group_settings.get_setting("activity_warn_minutes"))
    close_state = int(group_settings.get_setting("activity_close_minutes"))
    user_name = user.fullname

    # Определяем ответ в зависимости от текущего состояния настройки и нового состояния
    if current_state == new_timer:
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Предупреждение <b>уже через {new_timer} минут</b>"
        )
    else:
        if int(new_timer) < close_state:
            # Обновление настроек
            await questions_repo.settings.update_setting(
                group_id=message.chat.id, key="activity_warn_minutes", value=new_timer
            )
            response = (
                f"<b>✨ Изменение настроек форума</b>\n\n"
                f"Пользователь <b>{user_name}</b> установил предупреждение через {new_timer} минут"
            )
        else:
            response = (
                f"<b>✨ Изменение настроек форума</b>\n\n"
                f"Невозможно установить время предупреждения меньше или равному времени закрытия ({close_state} минут) "
            )

    await message.reply(response)


@main_topic_cmds_router.message(Command("close"), IsMainTopicMessageWithCommand())
async def timer_close_change(
    message: Message,
    command: CommandObject,
    user: Employee,
    questions_repo: QuestionsRequestsRepo,
):
    """Управление временем закрытия по бездействию."""
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Валидация аргументов команды
    if not command.args:
        await message.reply("Пример команды: /close [время в минутах]")
        return

    new_timer = command.args.split(maxsplit=1)[0]
    if type(int(new_timer)) is not int:
        await message.reply("Пример команды: /close [время в минутах]")
        return

    # Получаем текущие настройки
    group_settings = await questions_repo.settings.get_settings_by_group_id(
        group_id=message.chat.id
    )

    current_state = int(group_settings.get_setting("activity_close_minutes"))
    warn_state = int(group_settings.get_setting("activity_warn_minutes"))
    target_state = new_timer == current_state
    user_name = user.fullname

    # Определяем ответ в зависимости от текущего состояния настройки и нового состояния
    if current_state == target_state:
        response = (
            f"<b>✨ Изменение настроек форума</b>\n\n"
            f"Закрытие <b>уже {new_timer} минут</b>"
        )
    else:
        if int(new_timer) > warn_state:
            # Обновление настроек
            await questions_repo.settings.update_setting(
                group_id=message.chat.id, key="activity_close_minutes", value=new_timer
            )
            response = (
                f"<b>✨ Изменение настроек форума</b>\n\n"
                f"Пользователь <b>{user_name}</b> установил таймер закрытия на {new_timer} минут"
            )
        else:
            response = (
                f"<b>✨ Изменение настроек форума</b>\n\n"
                f"Невозможно установить время закрытия меньше или равному времени предупреждения ({warn_state} минут) "
            )

    await message.reply(response)


@main_topic_cmds_router.message(Command("emoji_open"), IsMainTopicMessageWithCommand())
async def emoji_open_change(message: Message, user: Employee):
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    custom_emojis = await message.bot.get_forum_topic_icon_stickers()
    await message.reply(
        "<b>Выбор эмодзи для открытых вопросов</b>",
        reply_markup=settings_emoji(
            emoji_key="emoji_open",
            custom_emojis=custom_emojis,
        ),
        parse_mode="HTML",
    )


@main_topic_cmds_router.message(
    Command("emoji_in_progress"), IsMainTopicMessageWithCommand()
)
async def emoji_in_progress_change(message: Message, user: Employee):
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    custom_emojis = await message.bot.get_forum_topic_icon_stickers()
    await message.reply(
        "<b>Выбор эмодзи для вопросов в работе</b>",
        reply_markup=settings_emoji(
            emoji_key="emoji_in_progress",
            custom_emojis=custom_emojis,
        ),
        parse_mode="HTML",
    )


@main_topic_cmds_router.message(
    Command("emoji_closed"), IsMainTopicMessageWithCommand()
)
async def emoji_closed_change(message: Message, user: Employee):
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    custom_emojis = await message.bot.get_forum_topic_icon_stickers()
    await message.reply(
        "<b>Выбор эмодзи для закрытых вопросов</b>",
        reply_markup=settings_emoji(
            emoji_key="emoji_closed",
            custom_emojis=custom_emojis,
        ),
        parse_mode="HTML",
    )


@main_topic_cmds_router.message(Command("emoji_fired"), IsMainTopicMessageWithCommand())
async def emoji_fired_change(message: Message, user: Employee):
    if user.role not in [2, 10]:
        await message.reply(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    custom_emojis = await message.bot.get_forum_topic_icon_stickers()
    await message.reply(
        "<b>Выбор эмодзи для отмененных вопросов</b>",
        reply_markup=settings_emoji(
            emoji_key="emoji_fired",
            custom_emojis=custom_emojis,
        ),
        parse_mode="HTML",
    )


@main_topic_cmds_router.callback_query(SettingsEmoji.filter())
async def handle_emoji_selection(
    callback: CallbackQuery,
    callback_data: SettingsEmoji,
    questions_repo: QuestionsRequestsRepo,
    user: Employee,
):
    if user.role not in [2, 10]:
        await callback.answer(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    # Обновляем настройки в БД
    await questions_repo.settings.update_setting(
        group_id=callback.message.chat.id,
        key=callback_data.emoji_key,
        value=callback_data.emoji_id,
    )

    # Получаем название измененного эмодзи для информирования
    emoji_names = {
        "emoji_open": "открытых вопросов",
        "emoji_in_progress": "вопросов в работе",
        "emoji_closed": "закрытых вопросов",
        "emoji_fired": "отмененных вопросов",
    }

    emoji_name = emoji_names.get(callback_data.emoji_key, callback_data.emoji_key)

    await callback.message.edit_text(
        f"✅ Эмодзи для {emoji_name} успешно изменено!", reply_markup=None
    )
    await callback.answer()


@main_topic_cmds_router.callback_query(SettingsEmojiPage.filter())
async def handle_emoji_page(
    callback: CallbackQuery, callback_data: SettingsEmojiPage, user: Employee
):
    if user.role not in [2, 10]:
        await callback.answer(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    custom_emojis = await callback.bot.get_forum_topic_icon_stickers()
    keyboard = settings_emoji(
        emoji_key=callback_data.emoji_key,
        custom_emojis=custom_emojis,
        page=callback_data.page,
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@main_topic_cmds_router.callback_query(F.data == "emoji_cancel")
async def handle_emoji_cancel(callback: CallbackQuery, user: Employee):
    if user.role not in [2, 10]:
        await callback.answer(
            "Доступ к изменению настроек форума есть только у РГ и администраторов 🥺"
        )
        return

    await callback.message.edit_text("❌ Выбор эмодзи отменен", reply_markup=None)
    await callback.answer()
