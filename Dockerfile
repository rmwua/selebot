FROM python:3.12-slim

WORKDIR /celebot

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python scripts/import_csv.py && python bot.py"]