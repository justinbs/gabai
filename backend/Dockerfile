# Slim, not alpine. Alpine uses musl, which has no manylinux wheels, so psycopg
# and onnxruntime would build from source and the image would take an hour.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first, so a code change does not reinstall onnxruntime every build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Models are not copied in. They are mounted at runtime, so a retrained model is
# a file swap and a restart rather than a rebuild, and the image stays small.

# Not root. If the app is ever compromised it should not own the filesystem.
RUN useradd --create-home --uid 1000 gabai \
    && mkdir -p /app/uploads /app/models \
    && chown -R gabai:gabai /app
USER gabai

EXPOSE 8000

# One worker. Both models load per worker, so a second one doubles ~640 MB of
# model memory for almost no throughput: onnxruntime releases the GIL and
# inference already runs in a threadpool.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
