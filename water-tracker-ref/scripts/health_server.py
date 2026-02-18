"""
Minimal health monitoring server for the WaterTracker watch app.

Endpoints:
  POST /api/water/report       — receives hydration status from the watch
  GET  /api/water/instruction   — returns a drinking instruction

Run:
  pip install -r requirements.txt
  python health_server.py

The server listens on 0.0.0.0:8080 by default.
Set API_TOKEN to secure the endpoints (watch sends Authorization: Bearer <token>).
"""

from flask import Flask, request, jsonify
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────
API_TOKEN = "your-secret-token"        # Set this to match Constants.DEFAULT_SERVER_TOKEN
WAKING_HOURS = 16                       # Assumed waking hours per day
# ───────────────────────────────────────────────────────────────

latest_report: dict = {}


def check_auth() -> bool:
    """Validate Bearer token from the Authorization header."""
    if not API_TOKEN:
        return True  # No token configured — allow all
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {API_TOKEN}"


@app.route("/api/water/report", methods=["POST"])
def water_report():
    """Receive hydration status from the watch."""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalid json"}), 400

    global latest_report
    latest_report = data
    print(
        f"[{data.get('timestamp', '?')}] "
        f"Intake: {data.get('current_intake', 0)} ml / {data.get('daily_goal', 0)} ml  "
        f"({data.get('entry_count', 0)} entries)"
    )
    return jsonify({"status": "ok"})


@app.route("/api/water/instruction", methods=["GET"])
def water_instruction():
    """Return a drinking instruction based on current hydration status."""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    current = int(request.args.get("current_intake", 0))
    goal = int(request.args.get("daily_goal", 2500))
    last_drink_raw = request.args.get("last_drink_time", "")

    now = datetime.now(timezone.utc)
    hours_passed = now.hour + now.minute / 60.0

    # Expected intake assuming linear distribution over waking hours
    expected = goal * min(hours_passed / WAKING_HOURS, 1.0)

    message = ""
    amount = 0
    priority = "none"
    deadline = 0

    # ── Rule 1: significantly behind schedule ──
    deficit = int(expected - current)
    if deficit > 500:
        amount = min(deficit, 500)
        message = f"Du bist {deficit} ml im Rückstand. Trink {amount} ml!"
        priority = "high" if deficit > 1000 else "normal"
        deadline = 30
    elif deficit > 200:
        amount = min(deficit, 300)
        message = f"Etwas im Rückstand ({deficit} ml). Trink {amount} ml."
        priority = "normal"
        deadline = 45

    # ── Rule 2: long time since last drink ──
    if not message and last_drink_raw:
        try:
            last_drink = parse_date(last_drink_raw)
            minutes_since = (now - last_drink).total_seconds() / 60.0
            if minutes_since > 120:
                message = "Über 2 Stunden seit dem letzten Trinken!"
                amount = 250
                priority = "high"
                deadline = 15
            elif minutes_since > 90:
                message = "Über 90 Min ohne Wasser — trink etwas!"
                amount = 200
                priority = "normal"
                deadline = 30
        except (ValueError, TypeError):
            pass

    # ── Rule 3: no drinks at all today ──
    if not message and current == 0 and hours_passed > 1:
        message = "Noch nichts getrunken heute — starte jetzt!"
        amount = 250
        priority = "high"
        deadline = 15

    return jsonify({
        "message": message,
        "recommended_amount": amount,
        "priority": priority,
        "deadline_minutes": deadline,
        "daily_target_override": 0,
        "timestamp": now.isoformat(),
    })


@app.route("/api/water/status", methods=["GET"])
def water_status():
    """Debug endpoint: returns the latest report received from the watch."""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(latest_report if latest_report else {"message": "no report yet"})


if __name__ == "__main__":
    print("Starting WaterTracker health server on :8080")
    print(f"API_TOKEN: {'set' if API_TOKEN else 'disabled (open access)'}")
    app.run(host="0.0.0.0", port=8080, debug=True)
