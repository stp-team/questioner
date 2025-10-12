import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)
from stp_database import create_engine, create_session_pool

from tgbot.config import Config, load_config
from tgbot.handlers import routers_list
from tgbot.middlewares.AdminRoleMiddleware import AdminRoleMiddleware
from tgbot.middlewares.ConfigMiddleware import ConfigMiddleware
from tgbot.middlewares.DatabaseMiddleware import DatabaseMiddleware
from tgbot.middlewares.MessagePairingMiddleware import MessagePairingMiddleware
from tgbot.middlewares.UserAccessMiddleware import UserAccessMiddleware
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import (
    remove_old_topics,
    scheduler,
)

bot_config = load_config(".env")

logger = logging.getLogger(__name__)


# async def on_startup(bot: Bot):
#     if bot_config.tg_bot.activity_status:
#         timeout_msg = f"Да ({bot_config.tg_bot.activity_warn_minutes}/{bot_config.tg_bot.activity_close_minutes} минут)"
#     else:
#         timeout_msg = "Нет"
#
#     if bot_config.tg_bot.remove_old_questions:
#         remove_topics_msg = (
#             f"Да (старше {bot_config.tg_bot.remove_old_questions_days} дней)"
#         )
#     else:
#         remove_topics_msg = "Нет"
#
#     await bot.send_message(
#         chat_id=bot_config.tg_bot.ntp_forum_id,
#         text=f"""<b>🚀 Запуск</b>
#
# Вопросник запущен со следующими параметрами:
# <b>- Направление:</b> {bot_config.tg_bot.division}
# <b>- Запрашивать регламент:</b> {"Да" if bot_config.tg_bot.ask_clever_link else "Нет"}
# <b>- Закрывать по таймауту:</b> {timeout_msg}
# <b>- Удалять старые вопросы:</b> {remove_topics_msg}
#
# <blockquote>База данных: {"Основная" if bot_config.db.main_db == "STPMain" else "Запасная"}</blockquote>""",
#     )


def register_middlewares(
    dp: Dispatcher,
    config: Config,
    bot: Bot,
    main_session_pool=None,
    questioner_session_pool=None,
):
    """Alternative setup with more selective middleware application.
    Use this if you want different middleware chains for different event types.
    """
    # Always needed
    config_middleware = ConfigMiddleware(config)
    database_middleware = DatabaseMiddleware(
        config=config,
        bot=bot,
        main_session_pool=main_session_pool,
        questioner_session_pool=questioner_session_pool,
    )

    # User management middlewares
    access_middleware = UserAccessMiddleware(bot=bot)
    role_middleware = AdminRoleMiddleware(bot=bot)

    # Apply to messages (most comprehensive chain)
    for middleware in [
        config_middleware,
        database_middleware,
        access_middleware,
        role_middleware,
    ]:
        dp.message.outer_middleware(middleware)

    # Apply to callback queries (skip role management if not needed)
    for middleware in [config_middleware, database_middleware, access_middleware]:
        dp.callback_query.outer_middleware(middleware)

    # Apply to edited messages (includes message pairing)
    for middleware in [
        config_middleware,
        database_middleware,
        access_middleware,
        role_middleware,
    ]:
        dp.edited_message.outer_middleware(middleware)
    dp.edited_message.outer_middleware(MessagePairingMiddleware())

    # Apply to chat member updates (minimal chain)
    for middleware in [config_middleware, database_middleware]:
        dp.chat_member.outer_middleware(middleware)


def get_storage(config):
    """Return storage based on the provided configuration.

    Args:
        config (Config): The configuration object.

    Returns:
        Storage: The storage object based on the configuration.

    """
    if config.tg_bot.use_redis:
        return RedisStorage.from_url(
            config.redis.dsn(),
            key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        )
    else:
        return MemoryStorage()


async def main():
    setup_logging()

    storage = get_storage(bot_config)

    bot = Bot(
        token=bot_config.tg_bot.token, default=DefaultBotProperties(parse_mode="HTML")
    )

    # Определение команд для приватных чатов
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="end", description="Закрыть вопрос"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )

    # Определение команд для групповых чатов
    await bot.set_my_commands(
        commands=[
            BotCommand(command="settings", description="Настройки форума"),
            BotCommand(command="release", description="Освободить вопрос"),
            BotCommand(command="end", description="Закрыть вопрос"),
        ],
        scope=BotCommandScopeAllGroupChats(),
    )

    # await bot.set_my_name(name="Вопросник")

    dp = Dispatcher(storage=storage)

    main_db_engine = create_engine(bot_config.db, db_name=bot_config.db.main_db)
    questioner_db_engine = create_engine(
        bot_config.db, db_name=bot_config.db.questioner_db
    )

    main_db = create_session_pool(main_db_engine)
    questioner_db = create_session_pool(questioner_db_engine)

    # Store session pools in dispatcher
    dp["main_db"] = main_db
    dp["questioner_db"] = questioner_db

    dp.include_routers(*routers_list)

    register_middlewares(dp, bot_config, bot, main_db, questioner_db)

    from tgbot.services.scheduler import register_scheduler_dependencies

    register_scheduler_dependencies(bot, questioner_db)

    if bot_config.questioner.remove_old_questions:
        scheduler.add_job(
            remove_old_topics,
            "interval",
            hours=12,
            args=[bot, questioner_db],
        )
    # await remove_old_topics(bot, questioner_db)
    scheduler.start()

    existing_jobs = scheduler.get_jobs()
    # scheduler.print_jobs()
    logger.info(
        f"[Redis] Найдено {len(existing_jobs)} существующих задач в планировщике"
    )

    # await on_startup(bot)
    try:
        await dp.start_polling(bot)
    finally:
        await main_db_engine.dispose()
        await questioner_db_engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot was interrupted by the user!")
