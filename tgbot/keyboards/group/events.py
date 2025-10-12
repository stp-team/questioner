from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class RemovedUser(CallbackData, prefix="removed_user"):
    action: str
    user_id: int | str
    role: int = None


def on_user_leave_kb(
    user_id: int | str,
    change_role: bool = False,
) -> InlineKeyboardMarkup:
    """Клавиатура для использования после удаления из группы
    :param user_id: Идентификатор пользователя Telegram
    :param change_role: Изменена ли роль пользователя
    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💬 ЛС",
                url=f"tg://user?id={user_id}",
            ),
        ]
    ]

    if change_role:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👑 Это РГ",
                    callback_data=RemovedUser(
                        action="change_role", user_id=user_id, role=2
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="👮‍♂️ Это старший",
                    callback_data=RemovedUser(
                        action="change_role", user_id=user_id, role=3
                    ).pack(),
                ),
            ],
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    return keyboard
