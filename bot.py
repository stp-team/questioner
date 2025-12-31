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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram_dialog import setup_dialogs
from aiohttp import web
from aiohttp.web import Response
from stp_database import create_engine, create_session_pool

from tgbot.config import Config, load_config
from tgbot.dialogs.menus import dialogs_list
from tgbot.handlers import routers_list
from tgbot.middlewares.ConfigMiddleware import ConfigMiddleware
from tgbot.middlewares.DatabaseMiddleware import DatabaseMiddleware
from tgbot.middlewares.MessagePairingMiddleware import MessagePairingMiddleware
from tgbot.middlewares.UserAccessMiddleware import UserAccessMiddleware
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import (
    register_scheduler_dependencies,
    remove_old_topics,
    scheduler,
)

bot_config = load_config(".env")

logger = logging.getLogger(__name__)


async def on_startup_webhook(bot: Bot, config: Config) -> None:
    """Настройка webhook при запуске бота.

    Args:
        bot: Экземпляр бота
        config: Конфигурация приложения
    """
    webhook_url = f"https://{config.tg_bot.webhook_domain}{config.tg_bot.webhook_path}"
    logger.info(f"[Вебхук] Устанавливаем вебхук: {webhook_url}")

    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=[
            "message",
            "callback_query",
            "inline_query",
            "my_chat_member",
            "chat_member",
            "chat_join_request",
        ],
        drop_pending_updates=True,
        secret_token=config.tg_bot.webhook_secret,
    )
    logger.info("[Вебхук] Вебхук установлен")


async def on_shutdown_webhook(bot: Bot) -> None:
    """Удаление webhook при остановке бота.

    Args:
        bot: Экземпляр бота
    """
    logger.info("[Вебхук] Удаляем вебхук...")
    await bot.delete_webhook()
    logger.info("[Вебхук] Вебхук удален")


async def health_check(_request) -> Response:
    """Эндпоинт для проверки здоровья приложения.

    Args:
        _request: HTTP запрос

    Returns:
        Response: HTTP ответ со статусом здоровья
    """
    return Response(text="OK", status=200)


def register_middlewares(
    dp: Dispatcher,
    config: Config,
    bot: Bot,
    main_session_pool=None,
    questioner_session_pool=None,
):
    config_middleware = ConfigMiddleware(config)
    database_middleware = DatabaseMiddleware(
        config=config,
        bot=bot,
        main_session_pool=main_session_pool,
        questioner_session_pool=questioner_session_pool,
    )

    # User management middlewares
    access_middleware = UserAccessMiddleware(bot=bot)
    message_pairing_middleware = MessagePairingMiddleware()

    # Apply to messages
    for middleware in [
        config_middleware,
        database_middleware,
        access_middleware,
        message_pairing_middleware,
    ]:
        dp.message.outer_middleware(middleware)
        dp.callback_query.outer_middleware(middleware)
        dp.edited_message.outer_middleware(middleware)


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
        token=bot_config.tg_bot.token,
        default=DefaultBotProperties(parse_mode="HTML", link_preview_is_disabled=True),
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

    dp = Dispatcher(storage=storage)

    stp_engine = create_engine(
        host=bot_config.db.host,
        port=bot_config.db.port,
        username=bot_config.db.user,
        password=bot_config.db.password,
        db_name=bot_config.db.main_db,
    )
    questioner_engine = create_engine(
        host=bot_config.db.host,
        port=bot_config.db.port,
        username=bot_config.db.user,
        password=bot_config.db.password,
        db_name=bot_config.db.questioner_db,
    )

    main_db = create_session_pool(stp_engine)
    questioner_db = create_session_pool(questioner_engine)

    # Store session pools in dispatcher
    dp["main_db"] = main_db
    dp["questioner_db"] = questioner_db

    dp.include_routers(*routers_list)
    dp.include_routers(*dialogs_list)
    # dp.include_routers(*common_dialogs_list)
    setup_dialogs(dp)

    register_middlewares(dp, bot_config, bot, main_db, questioner_db)

    register_scheduler_dependencies(bot, questioner_db, main_db)

    if bot_config.questioner.remove_old_questions:
        scheduler.add_job(
            remove_old_topics,
            "interval",
            hours=12,
            args=[bot, questioner_db],
        )
    scheduler.start()

    existing_jobs = scheduler.get_jobs()
    logger.info(
        f"[Redis] Найдено {len(existing_jobs)} существующих задач в планировщике"
    )

    try:
        if bot_config.tg_bot.use_webhook:
            # Webhook mode
            logger.info("[Режим запуска] Бот запущен в режиме webhooks")
            await on_startup_webhook(bot, bot_config)

            # Создаем aiohttp приложение
            app = web.Application()

            # Регистрируем health check эндпоинт
            app.router.add_get("/health", health_check)

            # Создаем обработчик webhook
            webhook_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=bot_config.tg_bot.webhook_secret,
            )
            webhook_handler.register(app, path="/")
            setup_application(app, dp, bot=bot)

            # Запускаем веб-сервер
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(
                runner, host="0.0.0.0", port=bot_config.tg_bot.webhook_port
            )
            await site.start()

            logger.info(
                f"[Вебхук] Сервер запущен на порту {bot_config.tg_bot.webhook_port}"
            )

            # Держим сервер запущенным
            await asyncio.Event().wait()

        else:
            # Polling mode
            logger.info("[Режим запуска] Бот запущен в режиме polling")
            await dp.start_polling(
                bot,
                allowed_updates=[
                    "message",
                    "callback_query",
                    "inline_query",
                    "my_chat_member",
                    "chat_member",
                    "chat_join_request",
                ],
            )
    finally:
        if bot_config.tg_bot.use_webhook:
            await on_shutdown_webhook(bot)
        await stp_engine.dispose()
        await questioner_engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot was interrupted by the user!")
