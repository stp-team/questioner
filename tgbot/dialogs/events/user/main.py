from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from tgbot.dialogs.states.user.main import QuestionSG


async def start_question_dialog(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(QuestionSG.question_text)
