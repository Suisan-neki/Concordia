FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip setuptools wheel \
    && pip install -e .

CMD ["uvicorn", "concordia.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
