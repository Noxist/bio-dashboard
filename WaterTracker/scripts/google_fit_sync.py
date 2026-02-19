#!/usr/bin/env python3
"""
google_fit_sync.py
------------------
Bridge script that reads the current daily water intake from Home Assistant
and writes the *delta* (new intake since last sync) to Google Fit as a
com.google.hydration data point.

Intended to run as a cron job, systemd timer, or Home Assistant shell_command.

Requirements (see requirements.txt):
    pip install google-auth google-auth-oauthlib google-api-python-client requests

First-time setup:
    1. Create a Google Cloud project at https://console.cloud.google.com
    2. Enable the "Fitness API"
    3. Create OAuth 2.0 Desktop credentials and download the JSON as
       credentials.json in the same folder as this script.
    4. Run the script once interactively -- it will open a browser for
       consent and cache a token.json for future headless runs.

Usage:
    export HA_URL="https://xxxxx.ui.nabu.casa"
    export HA_TOKEN="eyJ0eX..."
    python google_fit_sync.py

NOTE: Google deprecated the Fitness REST API in favour of Health Connect
(Android-only).  The REST API still works for server-side writes as of
early 2026 but may be removed in the future.  If it stops working, the
fallback is a tiny Android companion app that reads from HA and writes to
Health Connect -- see SETUP.md for details.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HA_URL: str = os.environ.get("HA_URL", "")
HA_TOKEN: str = os.environ.get("HA_TOKEN", "")
ENTITY_ID: str = "sensor.water_tracker_daily"

SCOPES = [
    "https://www.googleapis.com/auth/fitness.nutrition.write",
    "https://www.googleapis.com/auth/fitness.nutrition.read",
]

SCRIPT_DIR = Path(__file__).resolve().parent
CRED_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"
STATE_FILE = SCRIPT_DIR / ".last_synced_state.json"

DATA_SOURCE_ID_PREFIX = "derived:com.google.hydration:"
DATA_STREAM_NAME = "WaterTrackerWatch"


# ---------------------------------------------------------------------------
# Google Auth helpers
# ---------------------------------------------------------------------------
def get_google_credentials() -> Credentials:
    """Return valid Google OAuth2 credentials, refreshing or prompting as needed."""
    creds: Credentials | None = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CRED_FILE.exists():
                print(f"ERROR: {CRED_FILE} not found. Download OAuth Desktop "
                      "credentials from Google Cloud Console.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CRED_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# Home Assistant
# ---------------------------------------------------------------------------
def get_ha_water_ml() -> float | None:
    """Fetch current daily water intake (ml) from Home Assistant."""
    if not HA_URL or not HA_TOKEN:
        print("ERROR: Set HA_URL and HA_TOKEN environment variables.")
        return None

    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.get(f"{HA_URL}/api/states/{ENTITY_ID}", headers=headers, timeout=15)
        r.raise_for_status()
        state = r.json().get("state", "0")
        return float(state)
    except Exception as exc:
        print(f"ERROR reading HA: {exc}")
        return None


# ---------------------------------------------------------------------------
# Google Fit
# ---------------------------------------------------------------------------
def _headers(creds: Credentials) -> dict:
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def ensure_data_source(creds: Credentials) -> str | None:
    """Create (or find) the hydration data source and return its dataStreamId."""
    headers = _headers(creds)

    # Try to find an existing source first
    r = requests.get(
        "https://www.googleapis.com/fitness/v1/users/me/dataSources",
        headers=headers,
        params={"dataTypeName": "com.google.hydration"},
        timeout=15,
    )
    if r.status_code == 200:
        for src in r.json().get("dataSource", []):
            if DATA_STREAM_NAME in src.get("dataStreamId", ""):
                return src["dataStreamId"]

    # Create it
    body = {
        "dataStreamName": DATA_STREAM_NAME,
        "type": "derived",
        "application": {"name": "Water Tracker Watch", "version": "1"},
        "dataType": {"name": "com.google.hydration"},
        "device": {
            "manufacturer": "Huawei",
            "model": "Watch Ultimate 2",
            "type": "watch",
            "uid": "water-tracker-watch-1",
            "version": "1",
        },
    }
    r = requests.post(
        "https://www.googleapis.com/fitness/v1/users/me/dataSources",
        headers=headers,
        json=body,
        timeout=15,
    )
    if r.status_code in (200, 409):
        ds_id = r.json().get("dataStreamId")
        if ds_id:
            return ds_id
        # 409 = already exists but response doesn't include id, re-fetch
        return ensure_data_source(creds)

    print(f"ERROR creating data source: {r.status_code} {r.text}")
    return None


def write_hydration(creds: Credentials, ds_id: str, litres: float) -> bool:
    """Insert a single hydration data point (litres) into Google Fit."""
    headers = _headers(creds)
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    end_ns = now_ns + 1_000_000  # +1 ms

    dataset_id = f"{now_ns}-{end_ns}"
    body = {
        "minStartTimeNs": str(now_ns),
        "maxEndTimeNs": str(end_ns),
        "dataSourceId": ds_id,
        "point": [
            {
                "startTimeNanos": str(now_ns),
                "endTimeNanos": str(end_ns),
                "dataTypeName": "com.google.hydration",
                "value": [{"fpVal": litres}],
            }
        ],
    }

    url = (
        f"https://www.googleapis.com/fitness/v1/users/me/"
        f"dataSources/{ds_id}/datasets/{dataset_id}"
    )
    r = requests.patch(url, headers=headers, json=body, timeout=15)
    return r.status_code == 200


# ---------------------------------------------------------------------------
# Delta tracking
# ---------------------------------------------------------------------------
def load_last_synced() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"date": "", "total_ml": 0.0}


def save_last_synced(date: str, total_ml: float) -> None:
    STATE_FILE.write_text(json.dumps({"date": date, "total_ml": total_ml}))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ha_ml = get_ha_water_ml()
    if ha_ml is None:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    last = load_last_synced()

    # If the date rolled over, reset the baseline
    if last["date"] != today:
        last = {"date": today, "total_ml": 0.0}

    delta_ml = ha_ml - last["total_ml"]
    if delta_ml <= 0:
        print(f"No new intake to sync (HA={ha_ml} ml, last synced={last['total_ml']} ml).")
        return

    print(f"New intake since last sync: {delta_ml} ml")

    creds = get_google_credentials()
    ds_id = ensure_data_source(creds)
    if not ds_id:
        return

    delta_litres = delta_ml / 1000.0
    if write_hydration(creds, ds_id, delta_litres):
        save_last_synced(today, ha_ml)
        print(f"Synced {delta_ml} ml ({delta_litres:.3f} L) to Google Fit. "
              f"Total today: {ha_ml} ml.")
    else:
        print("ERROR: Failed to write to Google Fit.")


if __name__ == "__main__":
    main()
