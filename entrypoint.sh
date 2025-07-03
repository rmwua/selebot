#!/bin/sh
set -e

cd /app

echo ">>> Running migrations, DATABASE_URL=$DATABASE_URL"
echo ">>> Current directory: $(pwd)"
echo ">>> Listing files:"
ls -l

alembic current
alembic upgrade head

echo ">>> Exporting Postgres → Google Sheets"
python sheets_sync.py

echo ">>> Starting flask endpoint..."
gunicorn app:app --bind 0.0.0.0:8000 &

echo "Starting the bot..."
python bot.py
