from dataclasses import dataclass
from typing import Optional

from environs import Env
from sqlalchemy import URL


@dataclass
class TgBot:
    """Создает объект TgBot из переменных окружения.

    Attributes:
    ----------
    token : str
        Токен бота.
    use_redis : str
        Нужно ли использовать Redis.
    """

    token: str
    use_redis: bool

    use_webhook: bool
    webhook_domain: Optional[str] = None
    webhook_path: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_port: int = 8443

    @staticmethod
    def from_env(env: Env):
        """Создает объект TgBot из переменных окружения."""
        token = env.str("BOT_TOKEN")

        use_redis = env.bool("USE_REDIS")
        use_webhook = env.bool("USE_WEBHOOK", False)
        webhook_domain = env.str("WEBHOOK_DOMAIN", None)
        webhook_path = env.str("WEBHOOK_PATH", "/questioner")
        webhook_secret = env.str("WEBHOOK_SECRET", None)
        webhook_port = env.int("WEBHOOK_PORT", 8443)

        return TgBot(
            token=token,
            use_redis=use_redis,
            use_webhook=use_webhook,
            webhook_domain=webhook_domain,
            webhook_path=webhook_path,
            webhook_secret=webhook_secret,
            webhook_port=webhook_port,
        )


@dataclass
class ForumsConfig:
    """Класс конфигурации ForumsConfig.

    Attributes:
    ----------
    ntp_main_forum_id : str
        Идентификатор форума ТГ НТП
    ntp_trainee_forum_id : str
        Идентификатор форума ТГ НТП ОР
    nck_main_forum_id : str
        Идентификатор форума ТГ НЦК
    nck_trainee_forum_id : str
        Идентификатор форума ТГ НЦК ОР
    """

    ntp_main_forum_id: str
    ntp_trainee_forum_id: str
    nck_main_forum_id: str
    nck_trainee_forum_id: str

    @staticmethod
    def from_env(env: Env):
        """Создает объект ForumsConfig из переменных окружения."""
        ntp_main_forum_id = env.str("NTP_MAIN_FORUM_ID")
        ntp_trainee_forum_id = env.str("NTP_TRAINEE_FORUM_ID")
        nck_main_forum_id = env.str("NCK_MAIN_FORUM_ID")
        nck_trainee_forum_id = env.str("NCK_TRAINEE_FORUM_ID")

        return ForumsConfig(
            ntp_main_forum_id=ntp_main_forum_id,
            ntp_trainee_forum_id=ntp_trainee_forum_id,
            nck_main_forum_id=nck_main_forum_id,
            nck_trainee_forum_id=nck_trainee_forum_id,
        )


@dataclass
class QuestionerConfig:
    """Класс конфигурации QuestionerConfig.

    Attributes:
    ----------
    ask_clever_link : str
        Запрашивать ли регламент
    ntp_trainee_sheet_name : str
        Название листа в таблице НТП
    nck_trainee_spreadsheet_id : str
        Идентификатор таблицы НЦК
    nck_trainee_sheet_name : str
        Название листа в таблице НЦК
    """

    remove_old_questions: bool
    remove_old_questions_days: int

    @staticmethod
    def from_env(env: Env):
        """Создает объект QuestionerConfig из переменных окружения."""
        remove_old_questions = env.bool("REMOVE_OLD_QUESTIONS")
        remove_old_questions_days = env.int("REMOVE_OLD_QUESTIONS_DAYS")

        return QuestionerConfig(
            remove_old_questions=remove_old_questions,
            remove_old_questions_days=remove_old_questions_days,
        )


@dataclass
class DbConfig:
    """Класс конфигурации подключения к базе данных.
    Класс хранит в себе настройки базы

    Attributes:
    ----------
    host : str
        Хост, на котором находится база данных
    password : str
        Пароль для авторизации в базе данных
    user : str
        Логин для авторизации в базе данных
    main_db : str
        Имя основной базы данных
    questioner_db : str
        Имя базы данных вопросника
    """

    host: str
    port: int
    user: str
    password: str

    main_db: str
    questioner_db: str

    def construct_sqlalchemy_url(
        self,
        db_name=None,
        driver="aiomysql",
    ) -> URL:
        """Constructs and returns SQLAlchemy URL for MariaDB database connection"""
        connection_url = URL.create(
            f"mysql+{driver}",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port if self.port else 3306,
            database=db_name,
            query={
                "charset": "utf8mb4",
                "use_unicode": "1",
                "sql_mode": "TRADITIONAL",
                "connect_timeout": "30",
                "autocommit": "false",
            },
        )

        return connection_url

    @staticmethod
    def from_env(env: Env):
        """Создает объект DbConfig из переменных окружения."""
        host = env.str("DB_HOST")
        port = env.int("DB_PORT")
        user = env.str("DB_USER")
        password = env.str("DB_PASS")

        main_db = env.str("MAIN_DB_NAME")
        questioner_db = env.str("QUESTIONS_DB_NAME")

        return DbConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            main_db=main_db,
            questioner_db=questioner_db,
        )


@dataclass
class RedisConfig:
    """Класс конфигурации Redis.

    Attributes:
    ----------
    redis_pass : str
        Пароль для авторизации в Redis.
    redis_port : int
        Порт, на котором слушает сервер Redis.
    redis_host : str
        Хост, где запущен сервер Redis.
    redis_db : str
        Название базы
    """

    redis_host: str
    redis_port: int
    redis_db: str
    redis_pass: str

    def dsn(self) -> str:
        """Конструирует и возвращает Redis DSN (Data Source Name)."""
        if self.redis_pass:
            return f"redis://:{self.redis_pass}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @staticmethod
    def from_env(env: Env):
        """Создает объект RedisConfig из переменных окружения."""
        redis_pass = env.str("REDIS_PASSWORD")
        redis_port = env.int("REDIS_PORT")
        redis_host = env.str("REDIS_HOST")
        redis_db_name = env.str("REDIS_DB")

        return RedisConfig(
            redis_pass=redis_pass,
            redis_port=redis_port,
            redis_host=redis_host,
            redis_db=redis_db_name,
        )


@dataclass
class Config:
    """Основной конфигурационный класс, интегрирующий в себя другие классы.

    Этот класс содержит все настройки, и используется для доступа к переменным окружения.

    Attributes:
    ----------
    tg_bot : TgBot
        Хранит специфичные для бота настройки
    db : DbConfig
        Хранит специфичные для базы данных настройки (стандартно None)
    redis : RedisConfig
        Хранит специфичные для Redis настройки (стандартно None)
    """

    tg_bot: TgBot
    forum: ForumsConfig
    questioner: QuestionerConfig
    db: DbConfig
    redis: RedisConfig


def load_config(path: str | None = None) -> Config:
    """Эта функция принимает в качестве входных данных опциональный путь к файлу и возвращает объект Config.
    :param path: Путь к файлу env, из которого загружаются переменные конфигурации.
    Она считывает переменные окружения из файла .env, если он указан, в противном случае — из окружения процесса.
    :return: Объект Config с атрибутами, установленными в соответствии с переменными окружения.
    """
    # Создает объект Env.
    # Объект используется для чтения файла переменных окружения.
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot.from_env(env),
        forum=ForumsConfig.from_env(env),
        questioner=QuestionerConfig.from_env(env),
        db=DbConfig.from_env(env),
        redis=RedisConfig.from_env(env),
    )
