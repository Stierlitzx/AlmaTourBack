FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg + h3
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Runs migrations then starts the server
CMD ["sh", "-c", "alembic stamp head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]