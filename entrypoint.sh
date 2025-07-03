#!/bin/sh

set -e

cd /app

mkdir -p .keys
if [ -n "$GOOGLE_SA_KEY_B64" ]; then
  echo "$GOOGLE_SA_KEY_B64" | base64 -d > /app/.keys/sa.json
  export GOOGLE_SA_KEY_PATH=/app/.keys/sa.json
fi

echo ">>> Running migrations, DATABASE_URL=$DATABASE_URL"
echo ">>> Current directory: $(pwd)"
echo ">>> Listing files:"
ls -l

alembic current
alembic upgrade head

#echo ">>> Exporting Postgres → Google Sheets"
#python sheets_sync.py

echo ">>> Starting flask endpoint..."
gunicorn app:app --bind 0.0.0.0:8000 &

echo "Starting the bot..."
python bot.py
