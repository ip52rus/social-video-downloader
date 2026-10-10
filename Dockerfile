
FROM python:3.13-slim

WORKDIR /app

# Устанавливаем системный FFmpeg для объединения аудио и видео
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10

RUN pip install --no-cache-dir uv && pip cache purge || true

RUN uv venv /opt/venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_PYTHON_PREFERENCE=only-system
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

RUN python -c 'from aiogram.client.default import DefaultBotProperties; print("aiogram 3.x installed")' 2>/dev/null || \
    (uv pip install --python /opt/venv/bin/python "aiogram>=3.0.0" && echo 'aiogram 3.x installed')

RUN (uv cache prune 2>/dev/null || pip cache purge 2>/dev/null) || true
RUN pip cache purge || true

COPY . .

RUN python -c 'import sys; print("Python:", sys.version[:20]); print("PATH:", __import__("os").environ.get("PATH","")[:80])' && \
    python -c 'import site; print("site-packages:", site.getsitepackages())'

ENV DATA_DIR=/app/data
RUN mkdir -p /app/data && chmod 777 /app/data
RUN chown -R 1000:1000 /app/data || true

CMD ["/opt/venv/bin/python", "bot.py"]
