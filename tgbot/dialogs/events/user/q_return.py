from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from tgbot.dialogs.states.user.main import ReturnSG


async def start_q_return_dialog(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(ReturnSG.menu)


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
    await dialog_manager.switch_to(ReturnSG.confirmation)


async def on_confirm_return(
    callback: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    """Обработчик подтверждения возврата вопроса.

    Args:
        callback: Callback query from telegram
        _widget: Widget that triggered the event
        dialog_manager: Dialog manager instance
    """
    question_token = dialog_manager.dialog_data.get("question_token")

    if not question_token:
        await callback.answer("Ошибка: вопрос не выбран", show_alert=True)
        return

    # TODO: Здесь должна быть логика возврата вопроса в базе данных
    # Например: await questions_repo.questions.return_question(selected_question_id)

    await callback.answer("✅ Вопрос успешно возвращен!", show_alert=True)
    # Закрываем диалог или возвращаемся в меню
    await dialog_manager.done()


async def on_cancel_return(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    """Обработчик отмены возврата вопроса.

    Args:
        _event: Callback query from telegram
        _widget: Widget that triggered the event
        dialog_manager: Dialog manager instance
    """
    # Возвращаемся в меню выбора вопросов
    await dialog_manager.switch_to(ReturnSG.menu)
