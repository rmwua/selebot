import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME     = os.getenv("SHEET_NAME", "celebrities")
SA_KEY_PATH    = os.environ["GOOGLE_SA_KEY_PATH"]

# Авторизация и клиент API
_creds  = service_account.Credentials.from_service_account_file(
    SA_KEY_PATH,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
_service = build("sheets", "v4", credentials=_creds)
_sheets  = _service.spreadsheets()

def _get_sheet_id():
    """Numeric sheetId required for structural changes via batchUpdate."""
    resp = _sheets.get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets(properties(sheetId,title))"
    ).execute()
    for s in resp["sheets"]:
        props = s["properties"]
        if props["title"] == SHEET_NAME:
            return props["sheetId"]
    raise ValueError(f"Sheet '{SHEET_NAME}' not found")

_SHEET_ID = _get_sheet_id()


def push_row(record: dict, sheet_row: int | None = None):
    """
    1. Если sheet_row передан — обновляем именно ту строку.
    2. Иначе ищем record['id'] в столбце A и обновляем строку.
    3. Если не найдена — ищем первую пустую строку и затираем её.
    4. Если и пустых нет — append в конец.
    """
    str_id = str(record["id"])
    # читаем IDs со 2-й по 1000-ю строку
    resp     = _sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:A5000"
    ).execute()
    id_cells = resp.get("values", [])

    target = sheet_row
    if target is None:
        # ищем строку с этим id
        for i, row in enumerate(id_cells, start=2):
            if row and row[0] == str_id:
                target = i
                break
    if target is None:
        # ищем первую пустую
        for i, row in enumerate(id_cells, start=2):
            if not row or not row[0]:
                target = i
                break

    values = [[
        str_id,
        record["name"].title(),
        record["category"],
        record["geo"].title(),
        record["status"],
        record.get("reason", "")
    ]]

    if target is None:
        # append в конец
        _sheets.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:F",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values}
        ).execute()
    else:
        # update по точному диапазону A{target}:E{target}
        _sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A{target}:F{target}",
            valueInputOption="RAW",
            body={"values": values}
        ).execute()


def delete_row_by_id(record_id: int):
    """
    Удаляет строку, где в столбце A лежит record_id, смещая все ниже вверх.
    """
    str_id = str(record_id)
    # читаем IDs со 2-й по 1000-ю строку
    resp     = _sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:A5000"
    ).execute()
    id_cells = resp.get("values", [])

    sheet_row = None
    for i, row in enumerate(id_cells, start=2):
        if row and row[0] == str_id:
            sheet_row = i
            break

    if sheet_row is None:
        raise ValueError(f"ID {record_id} not found in column A")

    # batchUpdate для удаления строки
    body = {
        "requests": [{
            "deleteDimension": {
                "range": {
                    "sheetId": _SHEET_ID,
                    "dimension": "ROWS",
                    "startIndex": sheet_row - 1,
                    "endIndex": sheet_row
                }
            }
        }]
    }
    _sheets.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body
    ).execute()
