#!/bin/sh
set -e

echo ">>> Running migrations, DATABASE_URL=$DATABASE_URL"
alembic current
alembic upgrade head

echo "Importing CSV data..."
python scripts/import_csv.py

echo "Starting the bot..."
python bot.py
