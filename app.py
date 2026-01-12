import os
import asyncio
import traceback

from asyncpg import UniqueViolationError
from flask import Flask, request, abort, jsonify

from config import logger
from db.database_manager import DatabaseManager
from db.celebrity_service import CelebrityService
from sheets_client import push_row, push_rows

import socket
import urllib.request


app = Flask(__name__)
SHEET_WEBHOOK_SECRET = os.environ["SHEET_WEBHOOK_SECRET"]

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

loop.run_until_complete(DatabaseManager.init())
pool = loop.run_until_complete(DatabaseManager.get_pool())
service = CelebrityService(pool)


def process_single_row(row: dict, skip_push=False):
    action = row.get("action", "").strip().lower()

    raw_id = row.get("id")
    try:
        rec_id = int(raw_id)
    except (TypeError, ValueError):
        rec_id = None

    sheet_row = row.get("_row")
    try:
        sheet_row = int(sheet_row) if sheet_row is not None else None
    except (TypeError, ValueError):
        sheet_row = None

    if action == "delete":
        if not rec_id:
            raise ValueError("Missing id for delete")
        loop.run_until_complete(service.delete_by_id(rec_id))
        return {"deleted": rec_id}

    name_orig = row.get("name", "").strip()
    geo_orig  = row.get("geo", "").strip()

    name     = name_orig.lower()
    category = row.get("category", "").strip().lower()
    geo      = geo_orig.lower()
    status   = row.get("status", "").strip().lower()
    reason   = row.get("reason", "").strip() or None

    if not all([name, category, geo, status]):
        raise ValueError("Missing fields for upsert")

    try:
        if rec_id:
            existing = loop.run_until_complete(service.get_by_id(rec_id))
            if existing:
                if (
                    existing["name"] == name and
                    existing["category"] == category and
                    existing["geo"] == geo and
                    existing["status"] == status and
                    (existing.get("reason") or "") == (reason or "")
                ):
                    return None

            updated = loop.run_until_complete(
                service.update_by_id(
                    rec_id,
                    name=name,
                    category=category,
                    geo=geo,
                    status=status,
                    reason=reason
                )
            )
        else:
            updated = loop.run_until_complete(
                service.insert_celebrity(
                    name=name,
                    category=category,
                    geo=geo,
                    status=status,
                    reason=reason
                )
            )

        updated["_row"] = sheet_row
    except UniqueViolationError as e:
        logger.warning(f"Duplicate entry skipped: {e}")
        updated = loop.run_until_complete(service.find_celebrity(name, category, geo))

    if updated and not skip_push:
        push_row(updated, sheet_row)
    return updated


@app.route("/sheet-webhook", methods=["POST"])
def sheet_webhook():
    try:
        if request.headers.get("X-Webhook-Token") != SHEET_WEBHOOK_SECRET:
            abort(403)

        data = request.get_json(silent=True) or {}

        if "rows" in data:
            results = []
            for row in data["rows"]:
                try:
                    res = process_single_row(row, skip_push=True)
                    if res:
                        results.append(res)
                except Exception as e:
                    logger.error("Error in row:\n" + traceback.format_exc())
            if results:
                push_rows(results)
            return jsonify({"ok": True, "updated": len(results)})

        result = process_single_row(data)
        return jsonify({"ok": True, "data": result})

    except Exception:
        logger.error("Error in /sheet-webhook:\n" + traceback.format_exc())
        return jsonify({"ok": False, "error": "Server error"}), 500


@app.get("/diag/net")
def diag_net():
    out = {"ok": True, "checks": {}}

    # DNS check
    try:
        ip = socket.gethostbyname("oauth2.googleapis.com")
        out["checks"]["dns_oauth2"] = f"ok: {ip}"
    except Exception as e:
        out["ok"] = False
        out["checks"]["dns_oauth2"] = f"fail: {type(e).__name__}: {e}"

    # HTTPS check (quick)
    try:
        req = urllib.request.Request("https://oauth2.googleapis.com/token", method="POST")
        # Мы не отправляем валидный токен-запрос - нам важно, что соединение вообще установится.
        # Ожидаем 400/405, но не network unreachable.
        with urllib.request.urlopen(req, data=b"noop", timeout=5) as resp:
            out["checks"]["https_oauth2"] = f"ok: {resp.status}"
    except Exception as e:
        # тут норм может быть HTTPError 400 - это значит сеть есть
        if getattr(e, "code", None) is not None:
            out["checks"]["https_oauth2"] = f"ok-ish: HTTP {e.code}"
        else:
            out["ok"] = False
            out["checks"]["https_oauth2"] = f"fail: {type(e).__name__}: {e}"

    return out


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
