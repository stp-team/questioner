from typing import Any

from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const

from tgbot.dialogs.events.admin.stats import start_stats_extract
from tgbot.dialogs.states.admin.main import AdminSG

menu_window = Window(
    Const("""🛡️ <b>Управление ботом</b>

<i>Используй меню для взаимодействия с ботом</i>"""),
    Button(Const("📥 Выгрузка статистики"), id="stats", on_click=start_stats_extract),
    state=AdminSG.menu,
)


async def on_start(_on_start: Any, _dialog_manager: DialogManager, **_kwargs):
    """Установка параметров диалога по умолчанию при запуске.

    Args:
        _on_start: Дополнительные параметры запуска диалога
        _dialog_manager: Менеджер диалога
    """


admin_dialog = Dialog(
    menu_window,
    on_start=on_start,
)
