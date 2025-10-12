from typing import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from stp_database import Question

from tgbot.keyboards.admin.main import AdminMenu


class MainMenu(CallbackData, prefix="menu"):
    menu: str


class AskQuestionMenu(CallbackData, prefix="ask_question"):
    found_regulation: bool


class QuestionQualitySpecialist(CallbackData, prefix="q_quality_spec"):
    answer: bool = False
    token: str = None
    return_question: bool = False


class ReturnQuestion(CallbackData, prefix="return_q"):
    action: str
    token: str = None


class CancelQuestion(CallbackData, prefix="cancel_q"):
    action: str
    token: str


class ActivityStatusToggle(CallbackData, prefix="activity_toggle"):
    action: str  # "enable" или "disable"
    token: str


def user_kb(is_role_changed: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура главного меню.

    :param bool is_role_changed: Изменена ли роль пользователя
    :return: Объект встроенной клавиатуры для главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🤔 Задать вопрос", callback_data=MainMenu(menu="ask").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Возврат вопроса", callback_data=MainMenu(menu="return").pack()
            ),
        ]
    ]

    # Добавляем кнопку сброса если роль измененная
    if is_role_changed:
        buttons.append([
            InlineKeyboardButton(
                text="♻️ Сбросить роль", callback_data=AdminMenu(menu="reset").pack()
            ),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_kb() -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=MainMenu(menu="main").pack()
            ),
        ]
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def question_ask_kb(is_user_in_top: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для оформления вопроса.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    if is_user_in_top:
        buttons = [
            [
                InlineKeyboardButton(
                    text="↩️ Домой", callback_data=MainMenu(menu="main").pack()
                ),
            ]
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text="🤷‍♂️ Не нашел",
                    callback_data=AskQuestionMenu(found_regulation=False).pack(),
                ),
                InlineKeyboardButton(
                    text="↩️ Домой", callback_data=MainMenu(menu="main").pack()
                ),
            ]
        ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def cancel_question_kb(token: str) -> InlineKeyboardMarkup:
    """Клавиатура с отменой вопроса и возвратом в главное меню.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🙅‍♂️ Отменить вопрос",
                callback_data=CancelQuestion(action="cancel", token=token).pack(),
            ),
        ]
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def finish_question_kb() -> ReplyKeyboardMarkup:
    """Клавиатура с отменой вопроса и возвратом в главное меню.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            KeyboardButton(text="✅️ Закрыть вопрос"),
        ]
    ]

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )
    return keyboard


def question_quality_specialist_kb(
    token: str,
) -> InlineKeyboardMarkup:
    """Клавиатура оценки помощи с вопросом со стороны специалиста.

    :param str token: Уникальный токен вопроса
    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="👍 Да",
                callback_data=QuestionQualitySpecialist(
                    answer=True, token=token
                ).pack(),
            ),
            InlineKeyboardButton(
                text="👎 Нет",
                callback_data=QuestionQualitySpecialist(
                    answer=False, token=token
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔄 Вернуть вопрос",
                callback_data=QuestionQualitySpecialist(
                    return_question=True, token=token
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🤔 Новый вопрос", callback_data=MainMenu(menu="ask").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", callback_data=MainMenu(menu="main").pack()
            )
        ],
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def closed_question_specialist_kb(token: str) -> InlineKeyboardMarkup:
    """Клавиатура закрытого диалога для специалиста.

    :param token: Уникальный токен вопроса
    :return: Объект встроенной клавиатуры для закрытого диалога
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🤔 Новый вопрос", callback_data=MainMenu(menu="ask").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Вернуть вопрос",
                callback_data=QuestionQualitySpecialist(
                    return_question=True, token=token
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", callback_data=MainMenu(menu="main").pack()
            )
        ],
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def questions_list_kb(questions: Sequence[Question]) -> InlineKeyboardMarkup:
    """Клавиатура списка доступных к возврату вопросов

    :param Sequence[Question] questions: Список вопросов для отображения
    :return: Объект встроенной клавиатуры для закрытого диалога
    """
    buttons = []

    for question in questions:
        date_str = (
            question.end_time.strftime("%d.%m.%Y %H:%M")
            if question.end_time
            else question.start_time.strftime("%d.%m.%Y")
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"📅 {date_str} | {question.question_text}",
                callback_data=ReturnQuestion(
                    action="show", token=question.token
                ).pack(),
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="↩️ Назад", callback_data=MainMenu(menu="main").pack())
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def question_confirm_kb(token: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения возврата вопроса в работу

    :param str token: Уникальный токен вопроса
    :return: Объект встроенной клавиатуры для закрытого диалога
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Да, вернуть",
                callback_data=ReturnQuestion(action="confirm", token=token).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=MainMenu(menu="return").pack()
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def activity_status_toggle_kb(
    token: str,
    clever_link: str = None,
    current_status: bool = None,
    global_status: bool = True,
) -> InlineKeyboardMarkup:
    """Клавиатура переключения статуса активности для топика

    :param token: Уникальный токен вопроса
    :param user_id: Идентификатор пользователя Telegram
    :param clever_link: Ссылка на базу знаний
    :param current_status: Текущий статус активности для топика (None если не задан, используется глобальный)
    :param global_status: Глобальный статус активности из конфига
    :return: Объект встроенной клавиатуры для переключения статуса активности
    """
    # Определяем эффективный статус (персональный или глобальный)
    effective_status = current_status if current_status is not None else global_status

    if effective_status:
        # Если активность включена - предлагаем отключить
        button_text = "🟢 Автозакрытие включено"
        action = "disable"
    else:
        # Если активность отключена - предлагаем включить
        button_text = "🟠 Автозакрытие выключено"
        action = "enable"

    if clever_link:
        buttons = [
            [
                InlineKeyboardButton(
                    text="🗃️ Регламент",
                    url=clever_link,
                ),
            ],
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=ActivityStatusToggle(
                        action=action, token=token
                    ).pack(),
                ),
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=ActivityStatusToggle(
                        action=action, token=token
                    ).pack(),
                ),
            ]
        ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)
