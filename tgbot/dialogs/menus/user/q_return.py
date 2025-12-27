from typing import Any

from aiogram import F
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from tgbot.dialogs.events.user.q_return import (
    on_confirm_return,
    on_question_select,
)
from tgbot.dialogs.getters.user.q_return import confirmation_getter, return_getter
from tgbot.dialogs.states.user.main import ReturnSG
from tgbot.dialogs.widgets.buttons import HOME_BTN

menu_window = Window(
    Const(
        """🔄 <b>Возврат вопроса</b>
        
У тебя доступных к возврату вопросов :(""",
        when=~F["have_questions"],
    ),
    Format(
        """🔄 <b>Возврат вопроса</b>

К возврату доступно: {questions_length} вопрос(ов)

Выбери вопрос для возврата:""",
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
    getter=return_getter,
    state=ReturnSG.menu,
)

confirmation_window = Window(
    Format(
        """✅ <b>Подтверждение возврата</b>

❓ <b>Выбранный вопрос</b>
<blockquote>{text}</blockquote>

👮‍♂️ <b>Дежурный:</b> {duty}
🗃️ <b>Регламент:</b> {regulation}
🚀 <b>Начало диалога:</b> <code>{start_time}</code>
🔒 <b>Конец диалога:</b> <code>{end_time}</code>

<i>Токен вопроса: <code>{token}</code></i>

Вернуть этот вопрос?""",
        when=F["question"],
    ),
    Const(
        """❌ <b>Ошибка</b>

Вопрос не найден""",
        when=~F["question"],
    ),
    Button(
        Const("✅ Подтвердить возврат"),
        id="confirm_return",
        on_click=on_confirm_return,
        when=F["question"],
    ),
    Row(
        SwitchTo(
            Const("↩️ Назад"),
            id="cancel_return",
            state=ReturnSG.menu,
        ),
        HOME_BTN,
    ),
    getter=confirmation_getter,
    state=ReturnSG.confirmation,
)


async def on_start(_on_start: Any, _dialog_manager: DialogManager, **_kwargs):
    """Установка параметров диалога по умолчанию при запуске.

    Args:
        _on_start: Дополнительные параметры запуска диалога
        _dialog_manager: Менеджер диалога
    """


q_return_dialog = Dialog(
    menu_window,
    confirmation_window,
    on_start=on_start,
)
