FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: psycopg2 runtime needs libpq; ffmpeg is needed by yt-dlp to
# extract audio for the video-import speech-to-text path.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8000

# entrypoint runs `alembic upgrade head` then execs the command below.
# Invoked via `sh` so it works even when the host bind-mount drops the +x bit.
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
# Production server: gunicorn + uvicorn workers. PORT/WEB_CONCURRENCY come from env.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} -w ${WEB_CONCURRENCY:-2} --timeout 120 --access-logfile -"]
