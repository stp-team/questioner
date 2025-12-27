from typing import Any

from aiogram import F
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from tgbot.dialogs.events.user.history import on_question_select
from tgbot.dialogs.getters.user.history import details_getter, history_getter
from tgbot.dialogs.states.user.main import HistorySG
from tgbot.dialogs.widgets.buttons import HOME_BTN

menu_window = Window(
    Const(
        """📜 <b>История вопросов</b>

Ты еще не задавал вопросов""",
        when=~F["have_questions"],
    ),
    Format(
        """📜 <b>История вопросов</b>

Всего вопросов задано: {questions_length} вопрос(ов)""",
        when=F["have_questions"],
    ),
    ScrollingGroup(
        Select(
            Format("📅 {item.start_time} | {item.question_text}"),
            id="q_select",
            item_id_getter=lambda item: item.token,
            items="user_questions",
            on_click=on_question_select,
        ),
        id="questions_scroll",
        width=1,
        height=5,
        when=F["have_questions"],
    ),
    HOME_BTN,
    getter=history_getter,
    state=HistorySG.menu,
)

details_window = Window(
    Format(
        """❓ <b>О вопросе</b>

🤔 <b>Вопрошающий:</b> <b>{employee}</b>
👮‍♂️ <b>Дежурный:</b> <b>{duty}</b>

❓ <b>Изначальный вопрос:</b>
<blockquote expandable>{question.question_text}</blockquote>

🚀 <b>Начало диалога:</b> <code>{start_time}</code>
🔒 <b>Конец диалога:</b> <code>{end_time}</code>

🗃️ <b>Регламент:</b> {clever_link}
🔄 <b>Возврат:</b> {return}

<b>ID группы:</b> <code>{question.group_id}</code>
<b>ID темы:</b> <code>{question.topic_id}</code>
<b>Токен вопроса:</b> <code>{question.token}</code>""",
        when=F["question"],
    ),
    Const(
        """❌ <b>Ошибка</b>

Вопрос не найден""",
        when=~F["question"],
    ),
    Row(
        SwitchTo(
            Const("↩️ Назад"),
            id="back",
            state=HistorySG.menu,
        ),
        HOME_BTN,
    ),
    getter=details_getter,
    state=HistorySG.details,
)


async def on_start(_on_start: Any, _dialog_manager: DialogManager, **_kwargs):
    """Установка параметров диалога по умолчанию при запуске.

    Args:
        _on_start: Дополнительные параметры запуска диалога
        _dialog_manager: Менеджер диалога
    """


history_dialog = Dialog(menu_window, details_window, on_start=on_start)
