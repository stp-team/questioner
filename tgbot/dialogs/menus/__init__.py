"""Импорт всех диалогов и добавление их в dialogs_list."""

from tgbot.dialogs.menus.user.main import user_dialog
from tgbot.dialogs.menus.user.q_return import q_return_dialog
from tgbot.dialogs.menus.user.question import question_dialog

dialogs_list = [user_dialog, question_dialog, q_return_dialog]

common_dialogs_list = []

__all__ = ["dialogs_list", "common_dialogs_list"]
