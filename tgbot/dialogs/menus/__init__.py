"""Импорт всех диалогов и добавление их в dialogs_list."""

from tgbot.dialogs.menus.user.main import user_dialog

dialogs_list = [user_dialog]

common_dialogs_list = []

__all__ = ["dialogs_list", "common_dialogs_list"]
