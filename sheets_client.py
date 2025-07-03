from google.oauth2 import service_account
from googleapiclient.discovery import build
import os


SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME     = os.getenv("SHEET_NAME", "celebrities")
SA_KEY_PATH    = os.environ["GOOGLE_SA_KEY_PATH"]

_creds = service_account.Credentials.from_service_account_file(
    SA_KEY_PATH,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
_sheets = build("sheets", "v4", credentials=_creds).spreadsheets()


def push_row(record: dict, sheet_row: int | None = None):
    """
    Если sheet_row указан, правим именно эту строку,
    иначе fallback на id+1.
    """
    # 1) определяем целевую строку
    if sheet_row:
        row_index = sheet_row
    else:
        row_index = int(record["id"]) + 1

    # 2) готовим форматированные данные
    display_name = record["name"].title()
    display_geo  = record["geo"].title()
    values       = [[
        record["id"],
        display_name,
        record["category"],
        display_geo,
        record["status"],
    ]]

    # 3) пушим в A:E этой строки
    _sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{row_index}:E{row_index}",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
