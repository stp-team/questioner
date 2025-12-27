from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from tgbot.dialogs.states.user.main import HistorySG


async def start_history_dialog(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(HistorySG.menu)


async def on_question_select(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager, item_id: str
):
    """Обработчик выбора вопроса для возврата.

    Args:
        _event: Callback query from telegram
        _widget: Widget that triggered the event
        dialog_manager: Dialog manager instance
        item_id: ID of selected question
    """
    dialog_manager.dialog_data["question_token"] = item_id
    await dialog_manager.switch_to(HistorySG.details)
