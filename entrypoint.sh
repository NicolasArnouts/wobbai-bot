#!/bin/bash
set -e

echo "Starting Uvicorn (FastAPI)..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait until Uvicorn is ready by checking the health endpoint
echo "Waiting for Uvicorn to be ready..."
until curl -s http://localhost:8000/health | grep "healthy" > /dev/null; do
  echo "Uvicorn not ready yet. Sleeping 5 seconds..."
  sleep 5
done

echo "Uvicorn is up and running."

echo "Starting Celery worker..."
celery -A app.celery_app worker --loglevel=info &

echo "Starting Discord Bot..."
python discord_bot/bot.py &

# Wait for all background processes
wait 