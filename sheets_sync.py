import os
from dotenv import load_dotenv
import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build

def export_postgres_to_sheets():
    # 1) Загрузить .env
    load_dotenv()
    DATABASE_URL       = os.environ["DATABASE_URL"]
    GOOGLE_SA_KEY_PATH = os.environ["GOOGLE_SA_KEY_PATH"]
    SPREADSHEET_ID     = os.environ["SPREADSHEET_ID"]
    SHEET_NAME         = os.getenv("SHEET_NAME", "celebrities")

    # 2) Авторизация в Google Sheets API
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SA_KEY_PATH, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheets  = service.spreadsheets()

    # 3) Выгрузка из Postgres с id
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, geo, status, reason
                  FROM celebrities
                 ORDER BY id;
            """)
            rows = cur.fetchall()

    # 4) Формируем заголовок и данные
    header = ["id", "name", "category", "geo", "status", "reason"]
    rows_formatted = []
    for (rid, name, cat, geo, status, reason) in rows:
        rows_formatted.append([
            rid,
            name.title(),
            cat,
            geo.title(),
            status,
            reason or ""
        ])
    values = [header] + rows_formatted

    # 5) Очищаем старые данные в A1:E
    sheets.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1:E"
    ).execute()

    # 6) Записываем новые данные
    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    print(f"✅ Exported {len(rows)} rows (with id) to “{SHEET_NAME}” (A1:E).")


if __name__ == "__main__":
    export_postgres_to_sheets()
