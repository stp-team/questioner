FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.13-slim AS runtime

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
 && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev
COPY . .

# Добавляем виртуальное окружение в PATH
ENV PATH="/app/.venv/bin:$PATH"

# Запрет Python записывать файлы .pyc и использовать буферизацию stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "bot.py"]
