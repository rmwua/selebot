#!/bin/sh
set -e

cd /app

echo ">>> Running migrations, DATABASE_URL=$DATABASE_URL"
echo ">>> Current directory: $(pwd)"
echo ">>> Listing files:"
ls -l

alembic current
alembic upgrade head

echo "Importing CSV data..."
python scripts/import_csv.py

echo "Starting the bot..."
python bot.py
