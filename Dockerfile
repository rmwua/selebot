FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY entrypoint.sh /celebot/entrypoint.sh
RUN chmod +x /celebot/entrypoint.sh

EXPOSE 8000
CMD ["/celebot/entrypoint.sh"]