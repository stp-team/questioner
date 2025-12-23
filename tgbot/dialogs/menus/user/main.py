"""Генерация диалога для специалистов."""

from typing import Any

from aiogram import F
from aiogram_dialog import Dialog, DialogManager
from aiogram_dialog.widgets.kbd import (
    Button,
    Row,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.window import Window

from tgbot.dialogs.events.user.main import start_question_dialog
from tgbot.dialogs.getters.user.main import menu_getter
from tgbot.dialogs.states.user.main import UserSG

menu_window = Window(
    Const(
        """👋 <b>Привет</b>!
    
Не нашел тебя в списках сотрудников

Пройди авторизацию в @stpsher_bot и возвращайся""",
        when=~F["is_employee"],
    ),
    Format(
        """👋 <b>Привет</b>!

Я - бот-вопросник СТП

<b>❓ Задано вопросов:</b>
- За день {questions_count_day}
- За месяц {questions_count_month}

<i>Используй меню для взаимодействия с ботом</i>""",
        when="is_employee",
    ),
    Row(
        Button(
            Const("🤔 Задать вопрос"), id="question_new", on_click=start_question_dialog
        ),
        SwitchTo(Const("🔄 Возврат вопроса"), id="question_return", state=UserSG.menu),
        when="is_employee",
    ),
    getter=menu_getter,
    state=UserSG.menu,
)


async def on_start(_on_start: Any, _dialog_manager: DialogManager, **_kwargs):
    """Установка параметров диалога по умолчанию при запуске.

    Args:
        _on_start: Дополнительные параметры запуска диалога
        _dialog_manager: Менеджер диалога
    """


user_dialog = Dialog(
    menu_window,
    on_start=on_start,
)
