import asyncio
import logging
from typing import Union

from aiogram import Bot, exceptions
from aiogram.types import InlineKeyboardMarkup


async def send_message(
    bot: Bot,
    user_id: Union[int, str],
    text: str,
    disable_notification: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Безопасная рассылки сообщений

    :param bot: Экземпляр бота.
    :param user_id: Идентификатор пользователя Telegram. Если строка - должен содержать только цифры.
    :param text: Текст рассылки.
    :param disable_notification: Выключить или включить уведомление.
    :param reply_markup: Клавиатура.
    :return: Статус успешности.
    """
    try:
        await bot.send_message(
            user_id,
            text,
            disable_notification=disable_notification,
            reply_markup=reply_markup,
        )
    except exceptions.TelegramBadRequest:
        logging.error("Telegram server says - Bad Request: chat not found")
    except exceptions.TelegramForbiddenError:
        logging.error(f"Target [ID:{user_id}]: got TelegramForbiddenError")
    except exceptions.TelegramRetryAfter as e:
        logging.error(
            f"Target [ID:{user_id}]: Flood limit is exceeded. Sleep {e.retry_after} seconds."
        )
        await asyncio.sleep(e.retry_after)
        return await send_message(
            bot, user_id, text, disable_notification, reply_markup
        )  # Recursive call
    except exceptions.TelegramAPIError:
        logging.exception(f"Target [ID:{user_id}]: failed")
    else:
        logging.info(f"Target [ID:{user_id}]: success")
        return True
    return False


async def broadcast(
    bot: Bot,
    users: list[Union[str, int]],
    text: str,
    disable_notification: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> int:
    """Simple broadcaster.
    :param bot: Bot instance.
    :param users: List of users.
    :param text: Text of the message.
    :param disable_notification: Disable notification or not.
    :param reply_markup: Reply markup.
    :return: Count of messages.
    """
    count = 0
    try:
        for user_id in users:
            if await send_message(
                bot, user_id, text, disable_notification, reply_markup
            ):
                count += 1
            await asyncio.sleep(
                0.05
            )  # 20 messages per second (Limit: 30 messages per second)
    finally:
        logging.info(f"{count} messages successful sent.")
        return count
