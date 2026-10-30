FROM denoland/deno:2.9.7 AS deno-runtime

FROM python:3.13-slim

WORKDIR /app

# yt-dlp uses Deno for YouTube JavaScript challenge solving.
COPY --from=deno-runtime /usr/bin/deno /usr/local/bin/deno

RUN deno --version

# Устанавливаем системный FFmpeg для объединения аудио и видео
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10

RUN pip install --no-cache-dir uv

RUN uv venv /opt/venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_PYTHON_PREFERENCE=only-system
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --frozen --no-dev --no-install-project

RUN python -c 'from aiogram.client.default import DefaultBotProperties; print("aiogram 3.x installed")'

RUN (uv cache prune 2>/dev/null || pip cache purge 2>/dev/null) || true
RUN pip cache purge || true

COPY . .

RUN uv sync --frozen --no-dev

RUN python -c 'import sys; print("Python:", sys.version[:20]); print("PATH:", __import__("os").environ.get("PATH","")[:80])' && \
    python -c 'import site; print("site-packages:", site.getsitepackages())'


CMD ["/opt/venv/bin/python", "bot.py"]
