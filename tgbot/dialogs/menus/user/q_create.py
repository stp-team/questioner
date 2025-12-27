from typing import Any

from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Next, Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format, Multi
from magic_filter import F

from tgbot.dialogs.events.user.q_create import (
    link_error,
    on_confirm,
    on_message_input,
    validate_link,
)
from tgbot.dialogs.getters.user.q_create import confirmation_getter
from tgbot.dialogs.states.user.main import QuestionSG
from tgbot.dialogs.widgets.buttons import HOME_BTN

question_text = Window(
    Const("""🤔 <b>Суть вопроса</b>

Отправь вопрос и вложения одним сообщением"""),
    MessageInput(on_message_input),
    HOME_BTN,
    state=QuestionSG.question_text,
)


question_link = Window(
    Const("""🗃️ <b>Регламент</b>

Прикрепи ссылку на регламент из клевера, по которому у тебя вопрос"""),
    TextInput(
        id="link",
        type_factory=validate_link,
        on_success=Next(),
        on_error=link_error,
    ),
    Row(
        SwitchTo(
            Const("↩️ Назад"),
            id="back",
            state=QuestionSG.question_text,
        ),
        HOME_BTN,
    ),
    state=QuestionSG.question_link,
)


confirmation = Window(
    Multi(
        Format("""✅ <b>Подтверждение</b>

📝 <b>Твой вопрос:</b>
<blockquote>{user_text}</blockquote>"""),
        Format("\n📎 Есть прикрепленные файлы", when=F["has_attachments"]),
        Format("""

🔗 <b>Ссылка на регламент:</b>
<code>{link}</code>

Все верно?"""),
        sep="",
    ),
    Button(
        Const("✅ Подтвердить"),
        id="confirm_btn",
        on_click=on_confirm,
    ),
    Row(
        SwitchTo(
            Const("↩️ Назад"),
            id="back",
            state=QuestionSG.question_link,
        ),
        HOME_BTN,
    ),
    getter=confirmation_getter,
    state=QuestionSG.confirmation,
)


async def on_start(_on_start: Any, _dialog_manager: DialogManager, **_kwargs):
    """Установка параметров диалога по умолчанию при запуске.

    Args:
        _on_start: Дополнительные параметры запуска диалога
        _dialog_manager: Менеджер диалога
    """


question_dialog = Dialog(question_text, question_link, confirmation, on_start=on_start)
