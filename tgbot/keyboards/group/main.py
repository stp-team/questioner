from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from stp_database.models.Questions import Question


class QuestionQualityDuty(CallbackData, prefix="q_quality_duty"):
    answer: bool = False
    token: str = None
    return_question: bool = False


class QuestionAllowReturn(CallbackData, prefix="q_allow_return"):
    allow_return: bool = False
    token: str = None


class FinishedQuestion(CallbackData, prefix="finished_q"):
    action: str


def reopened_question_kb() -> InlineKeyboardMarkup:
    """Клавиатура с освобождением вопроса после переоткрытия

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🕊️ Освободить вопрос",
                callback_data=FinishedQuestion(action="release").pack(),
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    return keyboard


def question_finish_duty_kb(
    question: Question,
) -> InlineKeyboardMarkup:
    """Клавиатура оценки помощи с вопросом со стороны дежурного.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = []

    if question.quality_duty is None:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👎 Да",
                    callback_data=QuestionQualityDuty(
                        answer=False, token=question.token
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="👍 Нет",
                    callback_data=QuestionQualityDuty(
                        answer=True, token=question.token
                    ).pack(),
                ),
            ],
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 Вернуть вопрос",
                callback_data=QuestionQualityDuty(
                    return_question=True, token=question.token
                ).pack(),
            )
        ],
    )

    if question.allow_return:
        buttons.append([
            InlineKeyboardButton(
                text="🟢 Возврат разрешен",
                callback_data=QuestionAllowReturn(
                    token=question.token, allow_return=False
                ).pack(),
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🟠 Возврат отключен",
                callback_data=QuestionAllowReturn(
                    token=question.token, allow_return=True
                ).pack(),
            )
        ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def closed_question_duty_kb(
    token: str, allow_return: bool = True
) -> InlineKeyboardMarkup:
    """Клавиатура закрытого диалога для дежурного.

    :param token: Уникальный токен вопроса
    :type token: str
    :param allow_return: Разрешен ли специалисту возврат текущего вопроса
    :type allow_return: bool
    :return: Объект встроенной клавиатуры для закрытого диалога
    :rtype: InlineKeyboardMarkup
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Вернуть вопрос",
                callback_data=QuestionQualityDuty(
                    return_question=True, token=token
                ).pack(),
            )
        ]
    ]

    if allow_return:
        buttons.append([
            InlineKeyboardButton(
                text="🟢 Возврат разрешен",
                callback_data=QuestionAllowReturn(
                    token=token, allow_return=False
                ).pack(),
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🟠 Возврат отключен",
                callback_data=QuestionAllowReturn(
                    token=token, allow_return=True
                ).pack(),
            )
        ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard
