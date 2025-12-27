import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError

from tgbot.dialogs.states.admin.main import AdminSG
from tgbot.filters.admin import AdminFilter

admin_router = Router()
admin_router.message.filter(AdminFilter())
admin_router.message.filter(F.chat.type == "private")
admin_router.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@admin_router.message(CommandStart())
async def admin_start(
    _message: Message,
    dialog_manager: DialogManager,
) -> None:
    try:
        await dialog_manager.done()
    except NoContextError as exc:
        logger.debug("No active dialog to finish on /start: %s", exc)

    await dialog_manager.start(AdminSG.menu, mode=StartMode.RESET_STACK)
