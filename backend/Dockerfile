FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache postgresql-dev gcc musl-dev

COPY pyproject.toml .
RUN pip install --no-cache-dir psycopg2-binary && \
    pip install --no-cache-dir .

COPY backend/ .

EXPOSE 8000