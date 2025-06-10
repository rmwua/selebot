#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Importing CSV data..."
python scripts/import_csv.py

echo "Starting the bot..."
python bot.py
