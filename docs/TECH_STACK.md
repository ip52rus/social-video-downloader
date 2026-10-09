# Technology Baseline

## Runtime

- Python 3.13.
- uv manages the project environment, dependencies, and lockfile.
- The project uses a src/ layout.

## Application

- aiogram 3.x is the Telegram framework.
- yt-dlp is the initial media acquisition engine.
- Deno + yt-dlp-ejs are required for the validated YouTube extraction path.
- FFmpeg is required where downloaded video and audio streams must be assembled.

## Development quality

- pytest for tests.
- pytest-asyncio for asynchronous tests.
- Ruff for linting and formatting.
- GitHub Actions for CI.

## Dependency policy

Dependencies are declared in pyproject.toml and resolved into uv.lock.
Application dependencies are kept separate from development-only dependencies.
Version ranges are bounded to prevent accidental major-version migrations.

## Architecture policy

The Telegram framework is an adapter, not the downloader core.
Provider-specific behavior must remain behind provider interfaces.
Infrastructure such as Redis, queues, object storage, or distributed workers is not part of the initial baseline; it requires a measured requirement and an explicit architectural change.
