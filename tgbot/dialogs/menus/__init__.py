"""Импорт всех диалогов и добавление их в dialogs_list."""

from tgbot.dialogs.menus.admin.main import admin_dialog
from tgbot.dialogs.menus.user.history import history_dialog
from tgbot.dialogs.menus.user.main import user_dialog
from tgbot.dialogs.menus.user.q_create import question_dialog
from tgbot.dialogs.menus.user.q_return import q_return_dialog

dialogs_list = [
    user_dialog,
    question_dialog,
    q_return_dialog,
    history_dialog,
    admin_dialog,
]

common_dialogs_list = []

__all__ = ["dialogs_list", "common_dialogs_list"]
