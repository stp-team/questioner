from datetime import datetime

import pytz
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.keyboards.admin.main import AdminMenu


class MonthStatsExtract(CallbackData, prefix="month_stats"):
    menu: str
    month: int
    year: int


class DivisionStatsExtract(CallbackData, prefix="division_stats"):
    menu: str
    month: int
    year: int
    division: str


# Выбор дат для выгрузки статистики
def extract_kb() -> InlineKeyboardMarkup:
    current_date = datetime.now(tz=pytz.timezone("Asia/Yekaterinburg"))

    # Get month names in Russian
    month_names = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    buttons = []

    # Generate last 6 months in pairs (2 columns)
    for i in range(0, 6, 2):
        row = []

        # First month in the row
        year1 = current_date.year
        month1 = current_date.month - i
        if month1 <= 0:
            month1 += 12
            year1 -= 1

        month1_name = month_names[month1]
        row.append(
            InlineKeyboardButton(
                text=f"📅 {month1_name} {year1}",
                callback_data=MonthStatsExtract(
                    menu="month", month=month1, year=year1
                ).pack(),
            )
        )

        # Second month in the row (if exists)
        if i + 1 < 6:
            year2 = current_date.year
            month2 = current_date.month - (i + 1)
            if month2 <= 0:
                month2 += 12
                year2 -= 1

            month2_name = month_names[month2]
            row.append(
                InlineKeyboardButton(
                    text=f"📅 {month2_name} {year2}",
                    callback_data=MonthStatsExtract(
                        menu="month", month=month2, year=year2
                    ).pack(),
                )
            )

        buttons.append(row)

    # Add back button
    buttons.append([
        InlineKeyboardButton(
            text="↩️ Назад", callback_data=AdminMenu(menu="reset").pack()
        ),
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


# Выбор направления для выгрузки статистики
def division_selection_kb(month: int, year: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора направления для выгрузки статистики

    :param month: Выбранный месяц
    :param year: Выбранный год
    :return: Объект встроенной клавиатуры для выбора направления
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🏢 НЦК",
                callback_data=DivisionStatsExtract(
                    menu="division", month=month, year=year, division="НЦК"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="🏭 НТП",
                callback_data=DivisionStatsExtract(
                    menu="division", month=month, year=year, division="НТП"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Все направления",
                callback_data=DivisionStatsExtract(
                    menu="division", month=month, year=year, division="ВСЕ"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ К выбору месяца",
                callback_data=AdminMenu(menu="stats_extract").pack(),
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
