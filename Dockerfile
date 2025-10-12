FROM python:3.13-slim

WORKDIR /usr/src/app/questioner-bot

# Установка гита и других зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта для лучшего кеширования
COPY pyproject.toml uv.lock* /usr/src/app/questioner-bot/

# Установка зависимостей Python используя uv (создает .venv)
RUN uv sync --frozen

# Копирование кода проекта
COPY . /usr/src/app/questioner-bot

# Установка PATH для включения env
ENV PATH="/usr/src/app/questioner-bot/.venv/bin:$PATH"

CMD ["uv", "run", "python", "main.py"]
