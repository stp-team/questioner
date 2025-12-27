from typing import Any

from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const, Format, Multi
from magic_filter import F

from tgbot.dialogs.events.user.question import check_link, on_confirm, on_message_input
from tgbot.dialogs.getters.user.question import confirmation_getter
from tgbot.dialogs.states.user.main import QuestionSG

question_text = Window(
    Const("""🤔 <b>Суть вопроса</b>

Отправь вопрос и вложения одним сообщением"""),
    MessageInput(on_message_input),
    state=QuestionSG.question_text,
)


question_link = Window(
    Const("""🗃️ <b>Регламент</b>

Прикрепи ссылку на регламент из клевера, по которому у тебя вопрос"""),
    TextInput(
        id="link_input",
        on_success=check_link,
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
<code>{regulation_link}</code>

Все верно?"""),
        sep="",
    ),
    Button(
        Const("✅ Подтвердить"),
        id="confirm_btn",
        on_click=on_confirm,
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
