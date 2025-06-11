FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY entrypoint.sh /celebot/entrypoint.sh
RUN chmod +x /celebot/entrypoint.sh

CMD ["/celebot/entrypoint.sh"]
