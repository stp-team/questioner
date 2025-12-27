from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const

from tgbot.dialogs.events.user.main import close_all_dialogs

HOME_BTN = Button(Const("🏠 Домой"), id="home", on_click=close_all_dialogs)
