from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode

from tgbot.dialogs.states.user.main import UserSG


async def close_all_dialogs(
    _event: CallbackQuery, _widget: Any, dialog_manager: DialogManager
):
    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)
