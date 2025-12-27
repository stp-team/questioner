from aiogram.fsm.state import State, StatesGroup


class AdminSG(StatesGroup):
    """Группа состояний администраторов."""

    # Меню
    menu = State()
