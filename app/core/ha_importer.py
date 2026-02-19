"""
Home Assistant data importer.
Polls HA REST API for health sensor data and stores in SQLite.
"""

import logging
from datetime import datetime

import httpx

from app.config import HA_URL, HA_TOKEN, HA_SENSORS
from app.core.database import (
    insert_health_snapshot, get_latest_health_snapshot,
    insert_weight, get_latest_weight,
    insert_water_event, get_todays_water_total,
)

log = logging.getLogger("bio.ha_importer")


async def fetch_sensor_state(client: httpx.AsyncClient, entity_id: str) -> dict | None:
    """Fetch a single sensor state from HA REST API."""
    try:
        resp = await client.get(
            f"{HA_URL}/api/states/{entity_id}",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            state = data.get("state")
            if state in ("unknown", "unavailable", None):
                return None
            return {"state": state, "last_changed": data.get("last_changed")}
        else:
            log.warning("HA API returned %d for %s", resp.status_code, entity_id)
            return None
    except Exception as e:
        log.error("Error fetching %s: %s", entity_id, e)
        return None


def _parse_float(val: str | None) -> float | None:
    """Safely parse a float from HA state string."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: str | None) -> int | None:
    """Safely parse an int from HA state string."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


async def poll_and_store():
    """
    Poll all configured HA sensors and store a health snapshot.
    Only stores if at least one sensor returned data.
    """
    if not HA_TOKEN or "PASTE" in HA_TOKEN or len(HA_TOKEN) < 20:
        log.info("HA_TOKEN not configured, skipping health import")
        return

    if not HA_URL or "PASTE" in HA_URL:
        log.info("HA_URL not configured, skipping health import")
        return

    async with httpx.AsyncClient() as client:
        results = {}
        for key, entity_id in HA_SENSORS.items():
            # Skip non-sensor entities (boolean inputs)
            if entity_id.startswith("input_boolean."):
                data = await fetch_sensor_state(client, entity_id)
                if data:
                    results[key] = data["state"]
                continue

            data = await fetch_sensor_state(client, entity_id)
            if data:
                results[key] = data["state"]

    if not results:
        log.info("No sensor data received from HA, skipping snapshot")
        return

    # Build snapshot dict
    snapshot = {
        "heart_rate": _parse_float(results.get("heart_rate")),
        "resting_hr": _parse_float(results.get("resting_hr")),
        "hrv": _parse_float(results.get("hrv")),
        "sleep_duration": _parse_float(results.get("sleep_duration")),
        "sleep_confidence": _parse_float(results.get("sleep_confidence")),
        "spo2": _parse_float(results.get("spo2")),
        "respiratory_rate": _parse_float(results.get("respiratory_rate")),
        "steps": _parse_int(results.get("steps")),
        "calories": _parse_float(results.get("calories")),
    }

    # Only store if we got at least one real value
    has_data = any(v is not None for v in snapshot.values())
    if not has_data:
        log.info("All sensor values were None, skipping snapshot")
        return

    row_id = insert_health_snapshot(snapshot, source="ha")
    log.info(
        "Stored health snapshot #%d: hr=%s rhr=%s hrv=%s sleep=%s steps=%s",
        row_id,
        snapshot.get("heart_rate"),
        snapshot.get("resting_hr"),
        snapshot.get("hrv"),
        snapshot.get("sleep_duration"),
        snapshot.get("steps"),
    )

    # --- Weight import from Google Fit (via HealthSync) ---
    weight_str = results.get("user_weight")
    is_google_fit = bool(weight_str)
    if not weight_str:
        weight_str = results.get("user_weight_fallback")
    if weight_str:
        weight_val = _parse_float(weight_str)
        if weight_val and weight_val > 30:
            # Google Fit sensor reports weight in grams (e.g. 93800.0 g)
            # Convert to kg if the value is implausibly high for kg
            if weight_val > 500:
                weight_val = weight_val / 1000.0
                log.info("Converted weight from grams: %.1f kg", weight_val)
            latest_weight = get_latest_weight()
            if not latest_weight or abs(latest_weight.get("weight_kg", 0) - weight_val) > 0.05:
                source = "google_fit" if is_google_fit else "ha"
                insert_weight(weight_val, source=source)
                log.info("Updated weight from %s: %.1f kg", source, weight_val)

    # --- Water sensor import from HA ---
    water_str = results.get("water_daily")
    if water_str:
        water_val = _parse_float(water_str)
        if water_val and water_val > 0:
            current_total = get_todays_water_total()
            delta = int(water_val) - current_total
            if delta > 0:
                insert_water_event(delta, source="ha")
                log.info("Imported water delta from HA: +%d ml (total: %d)", delta, int(water_val))


async def fetch_intake_events_from_ha():
    """
    Check HA for intake button presses (elvanse/mate).
    This reads input_button state changes.
    To be called from webhook handler.
    """
    # This is handled via webhook from HA -> our API,
    # not by polling. See API routes.
    pass
