from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager


async def start_stats_extract(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    """Handler for stats extract button from admin dialog.

    Closes the current dialog and triggers the existing stats extraction handler.
    """
    # Close the dialog first
    await dialog_manager.done()

    # Import and trigger the existing handler
    from tgbot.handlers.admin.stats_extract import extract_stats

    await extract_stats(_event)
