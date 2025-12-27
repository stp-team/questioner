from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class AdminMenu(CallbackData, prefix="admin_menu"):
    menu: str


class SelectDivision(CallbackData, prefix="select_division"):
    division: str


# Основная клавиатура для команды /start
def admin_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="📥 Выгрузка статистики",
                callback_data=AdminMenu(menu="stats_extract").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🎭 Изменить роль",
                callback_data=AdminMenu(menu="change_role").pack(),
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def division_selection_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора направления при смене роли админа"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🏢 НЦК", callback_data=SelectDivision(division="НЦК").pack()
            ),
            InlineKeyboardButton(
                text="👶 НЦК ОР", callback_data=SelectDivision(division="НЦК ОР").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏭 НТП", callback_data=SelectDivision(division="НТП").pack()
            ),
            InlineKeyboardButton(
                text="👶 НТП ОР", callback_data=SelectDivision(division="НТП ОР").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=AdminMenu(menu="main").pack()
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
