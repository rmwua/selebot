import os
import asyncio
import traceback
from flask import Flask, request, abort, jsonify

from config import logger
from db.database_manager import DatabaseManager
from db.celebrity_service import CelebrityService
from sheets_client import push_row

app = Flask(__name__)
SHEET_WEBHOOK_SECRET = os.environ["SHEET_WEBHOOK_SECRET"]

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

loop.run_until_complete(DatabaseManager.init())
pool = loop.run_until_complete(DatabaseManager.get_pool())
service = CelebrityService(pool)


@app.route("/sheet-webhook", methods=["POST"])
def sheet_webhook():
    try:
        if request.headers.get("X-Webhook-Token") != SHEET_WEBHOOK_SECRET:
            abort(403)

        data = request.get_json(silent=True) or {}

        action = data.get("action", "").strip().lower()

        raw_id = data.get("id")
        try:
            rec_id = int(raw_id)
        except (TypeError, ValueError):
            rec_id = None

        sheet_row = data.get("_row")
        try:
            sheet_row = int(sheet_row) if sheet_row is not None else None
        except (TypeError, ValueError):
            sheet_row = None

        if action == "delete":
            if not rec_id:
                abort(400, "Missing id for delete")
            loop.run_until_complete(service.delete_by_id(rec_id))
            return jsonify({"ok": True})

        name_orig = data.get("name", "").strip()
        geo_orig  = data.get("geo",  "").strip()

        name     = name_orig.lower()
        category = data.get("category", "").strip().lower()
        geo      = geo_orig.lower()
        status   = data.get("status",   "").strip().lower()
        reason   = data.get("reason", "").strip() or None

        if not all([name, category, geo, status]):
            abort(400, "Missing fields for upsert")

        if rec_id:
            updated = loop.run_until_complete(
                service.update_by_id(rec_id,
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

        push_row(updated, sheet_row)
        return jsonify({"ok": True})

    except Exception as e:
        logger.error("Error in /sheet-webhook:\n" + traceback.format_exc())
        return jsonify({"ok": False, "error": str(e)}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
