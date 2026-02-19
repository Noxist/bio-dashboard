"""
FastAPI API routes for Bio-Dashboard.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import (
    API_KEY, ELVANSE_DEFAULT_DOSE_MG, MATE_CAFFEINE_MG,
    MEDIKINET_DEFAULT_DOSE_MG, MEDIKINET_RETARD_DEFAULT_DOSE_MG,
    CO_DAFALGAN_DEFAULT_DOSE_MG,
    USER_WEIGHT_KG, USER_HEIGHT_CM, USER_AGE, USER_IS_FASTING,
    WATER_WATCH_TOKEN,
)
from app.core.database import (
    insert_intake,
    insert_subjective_log,
    insert_health_snapshot,
    insert_meal,
    query_intakes,
    query_subjective_logs,
    query_health_snapshots,
    query_meals,
    get_latest_intake,
    get_latest_health_snapshot,
    get_todays_intakes,
    get_todays_logs,
    get_todays_meals,
    delete_intake,
    delete_subjective_log,
    delete_meal,
    # Water tracking
    insert_water_event,
    query_water_events,
    get_todays_water_events,
    get_todays_water_total,
    get_last_water_event,
    delete_water_event,
    reset_todays_water,
    upsert_water_goal,
    get_water_goal,
    get_water_goals_range,
    # Weight tracking
    insert_weight,
    get_latest_weight,
    query_weight_log,
)
from app.core.bio_engine import (
    compute_bio_score, generate_day_curve,
    elvanse_effect_curve, check_ddi_warnings,
)
from app.core.water_engine import (
    compute_daily_goal,
    assess_hydration,
    check_intake_velocity,
    detect_dehydration_from_vitals,
    hydration_bio_score_modifier,
    generate_hydration_curve,
)

router = APIRouter(prefix="/api")


# --- Auth ---

def verify_api_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Models ---

class IntakeRequest(BaseModel):
    substance: str = Field(..., pattern="^(elvanse|mate|medikinet|medikinet_retard|co_dafalgan|other)$")
    dose_mg: Optional[float] = None
    notes: str = ""
    timestamp: Optional[str] = None


class MealRequest(BaseModel):
    meal_type: str = Field(..., pattern="^(fruehstueck|mittagessen|abendessen|snack)$")
    notes: str = ""
    timestamp: Optional[str] = None


class SubjectiveLogRequest(BaseModel):
    focus: int = Field(..., ge=1, le=10)
    mood: int = Field(..., ge=1, le=10)
    energy: int = Field(..., ge=1, le=10)
    appetite: Optional[int] = Field(None, ge=1, le=10)
    inner_unrest: Optional[int] = Field(None, ge=1, le=10)
    # Migraene-Tracking (IHS-Kriterien)
    pain_severity: Optional[int] = Field(None, ge=0, le=10)
    aura_duration_min: Optional[int] = Field(None, ge=0)
    aura_type: Optional[str] = Field(None, pattern="^(zickzack|skotome|flimmern|other|)$")
    photophobia: Optional[bool] = None
    phonophobia: Optional[bool] = None
    tags: list[str] = []
    timestamp: Optional[str] = None


class HealthSnapshotRequest(BaseModel):
    heart_rate: Optional[float] = None
    resting_hr: Optional[float] = None
    hrv: Optional[float] = None
    sleep_duration: Optional[float] = None
    sleep_confidence: Optional[float] = None
    spo2: Optional[float] = None
    respiratory_rate: Optional[float] = None
    steps: Optional[int] = None
    calories: Optional[float] = None
    source: str = "manual"
    timestamp: Optional[str] = None


class BioScoreRequest(BaseModel):
    timestamp: Optional[str] = None
    sleep_duration_min: Optional[float] = None
    sleep_confidence: Optional[float] = None


# --- Endpoints ---

@router.post("/intake", dependencies=[Depends(verify_api_key)])
def log_intake(req: IntakeRequest):
    """Log a substance intake event."""
    # Set default doses
    dose = req.dose_mg
    if dose is None:
        if req.substance == "elvanse":
            dose = ELVANSE_DEFAULT_DOSE_MG
        elif req.substance == "mate":
            dose = MATE_CAFFEINE_MG
        elif req.substance == "medikinet":
            dose = MEDIKINET_DEFAULT_DOSE_MG
        elif req.substance == "medikinet_retard":
            dose = MEDIKINET_RETARD_DEFAULT_DOSE_MG
        elif req.substance == "co_dafalgan":
            dose = CO_DAFALGAN_DEFAULT_DOSE_MG

    row_id = insert_intake(req.substance, dose, req.notes, req.timestamp)

    # Check DDI warnings on intake
    ddi_warnings = []
    if req.substance == "co_dafalgan":
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        intakes = query_intakes(f"{today}T00:00:00", f"{today}T23:59:59")
        ddi_warnings = check_ddi_warnings(intakes, now, weight_kg=_get_effective_weight())

    result = {"id": row_id, "substance": req.substance, "dose_mg": dose, "status": "ok"}
    if ddi_warnings:
        result["warnings"] = ddi_warnings
    return result


@router.post("/log", dependencies=[Depends(verify_api_key)])
def log_subjective(req: SubjectiveLogRequest):
    """Log a subjective assessment (focus, mood, energy, appetite, inner_unrest, migraine)."""
    tags_json = json.dumps(req.tags)
    row_id = insert_subjective_log(
        req.focus, req.mood, req.energy, tags_json, req.timestamp,
        appetite=req.appetite, inner_unrest=req.inner_unrest,
        pain_severity=req.pain_severity,
        aura_duration_min=req.aura_duration_min,
        aura_type=req.aura_type if req.aura_type else None,
        photophobia=int(req.photophobia) if req.photophobia is not None else None,
        phonophobia=int(req.phonophobia) if req.phonophobia is not None else None,
    )
    return {"id": row_id, "status": "ok"}


@router.post("/health", dependencies=[Depends(verify_api_key)])
def log_health(req: HealthSnapshotRequest):
    """Log a health data snapshot manually."""
    data = req.model_dump(exclude={"source", "timestamp"})
    row_id = insert_health_snapshot(data, req.source, req.timestamp)
    return {"id": row_id, "status": "ok"}


@router.get("/intake", dependencies=[Depends(verify_api_key)])
def get_intakes(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: bool = False,
):
    """Query intake events."""
    if today:
        return get_todays_intakes()
    if start and end:
        return query_intakes(start, end)
    # Default: last 24h
    now = datetime.now()
    return query_intakes(
        (now - timedelta(hours=24)).isoformat(),
        now.isoformat(),
    )


@router.get("/intake/latest", dependencies=[Depends(verify_api_key)])
def get_latest_intake_route(substance: str = "elvanse"):
    """Get the most recent intake of a substance."""
    result = get_latest_intake(substance)
    if not result:
        return {"found": False}
    return {"found": True, **result}


@router.get("/log", dependencies=[Depends(verify_api_key)])
def get_logs(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: bool = False,
):
    """Query subjective logs."""
    if today:
        return get_todays_logs()
    if start and end:
        return query_subjective_logs(start, end)
    now = datetime.now()
    return query_subjective_logs(
        (now - timedelta(hours=24)).isoformat(),
        now.isoformat(),
    )


@router.get("/health", dependencies=[Depends(verify_api_key)])
def get_health(
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Query health snapshots."""
    if start and end:
        return query_health_snapshots(start, end)
    now = datetime.now()
    return query_health_snapshots(
        (now - timedelta(hours=24)).isoformat(),
        now.isoformat(),
    )


@router.get("/health/latest", dependencies=[Depends(verify_api_key)])
def get_latest_health_route():
    """Get the most recent health snapshot."""
    result = get_latest_health_snapshot()
    if not result:
        return {"found": False}
    return {"found": True, **result}


@router.get("/bio-score", dependencies=[Depends(verify_api_key)])
def get_bio_score(
    timestamp: Optional[str] = None,
    sleep_duration_min: Optional[float] = None,
    sleep_confidence: Optional[float] = None,
):
    """
    Compute Bio-Score for a given timestamp (default: now).
    Uses today's intake history to calculate substance effects.
    """
    target = datetime.fromisoformat(timestamp) if timestamp else datetime.now()

    # Get today's intakes for curve calculation
    today = target.strftime("%Y-%m-%d")
    intakes = query_intakes(f"{today}T00:00:00", f"{today}T23:59:59")

    # Dynamic weight from DB / Google Fit
    weight = _get_effective_weight()

    # Get health data (sleep + HRV) from latest snapshot if not provided
    hrv_ms = None
    resting_hr = None
    if sleep_duration_min is None:
        latest = get_latest_health_snapshot()
        if latest:
            sleep_duration_min = latest.get("sleep_duration")
            if sleep_confidence is None:
                sleep_confidence = latest.get("sleep_confidence")
            hrv_ms = latest.get("hrv")
            resting_hr = latest.get("resting_hr")

    result = compute_bio_score(
        target, intakes, sleep_duration_min, sleep_confidence,
        hrv_ms=hrv_ms, resting_hr=resting_hr,
        water_intake_ml=get_todays_water_total(),
        water_goal_ml=_compute_today_goal().get("goal_ml"),
        weight_kg=weight,
    )
    return result


@router.get("/bio-score/curve", dependencies=[Depends(verify_api_key)])
def get_bio_curve(
    date: Optional[str] = None,
    interval: int = Query(default=15, ge=5, le=60),
    sleep_duration_min: Optional[float] = None,
    sleep_confidence: Optional[float] = None,
):
    """
    Generate Bio-Score curve for a full day.
    Returns data points at the given interval (minutes).
    """
    if date:
        target_date = datetime.fromisoformat(date)
    else:
        target_date = datetime.now()

    day_str = target_date.strftime("%Y-%m-%d")
    intakes = query_intakes(f"{day_str}T00:00:00", f"{day_str}T23:59:59")

    # Dynamic weight from DB / Google Fit
    weight = _get_effective_weight()

    # Health data (sleep + HRV)
    hrv_ms = None
    resting_hr = None
    if sleep_duration_min is None:
        latest = get_latest_health_snapshot()
        if latest:
            sleep_duration_min = latest.get("sleep_duration")
            if sleep_confidence is None:
                sleep_confidence = latest.get("sleep_confidence")
            hrv_ms = latest.get("hrv")
            resting_hr = latest.get("resting_hr")

    curve = generate_day_curve(
        target_date, intakes, sleep_duration_min, sleep_confidence, interval,
        hrv_ms=hrv_ms, resting_hr=resting_hr, weight_kg=weight,
    )
    return {"date": day_str, "interval_minutes": interval, "points": curve}


@router.post("/webhook/ha/intake", dependencies=[Depends(verify_api_key)])
def ha_intake_webhook(req: IntakeRequest):
    """
    Webhook endpoint for HA automations.
    Triggered when intake button is pressed in HA.
    """
    dose = req.dose_mg
    if dose is None:
        if req.substance == "elvanse":
            dose = ELVANSE_DEFAULT_DOSE_MG
        elif req.substance == "mate":
            dose = MATE_CAFFEINE_MG
        elif req.substance == "medikinet":
            dose = MEDIKINET_DEFAULT_DOSE_MG
        elif req.substance == "medikinet_retard":
            dose = MEDIKINET_RETARD_DEFAULT_DOSE_MG
        elif req.substance == "co_dafalgan":
            dose = CO_DAFALGAN_DEFAULT_DOSE_MG

    row_id = insert_intake(req.substance, dose, req.notes, req.timestamp)
    print(
        f"[bio-api] HA webhook: {req.substance} {dose}mg logged (#{row_id})",
        flush=True,
    )
    return {"id": row_id, "status": "ok"}


@router.delete("/intake/{intake_id}", dependencies=[Depends(verify_api_key)])
def delete_intake_route(intake_id: int):
    """Delete an intake event by ID."""
    deleted = delete_intake(intake_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Intake not found")
    return {"deleted": intake_id, "status": "ok"}


@router.delete("/log/{log_id}", dependencies=[Depends(verify_api_key)])
def delete_log_route(log_id: int):
    """Delete a subjective log by ID."""
    deleted = delete_subjective_log(log_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"deleted": log_id, "status": "ok"}


@router.post("/meal", dependencies=[Depends(verify_api_key)])
def log_meal(req: MealRequest):
    """Log a meal event."""
    row_id = insert_meal(req.meal_type, req.notes, req.timestamp)
    return {"id": row_id, "meal_type": req.meal_type, "status": "ok"}


@router.get("/meal", dependencies=[Depends(verify_api_key)])
def get_meals(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: bool = False,
):
    """Query meal events."""
    if today:
        return get_todays_meals()
    if start and end:
        return query_meals(start, end)
    now = datetime.now()
    return query_meals(
        (now - timedelta(hours=24)).isoformat(),
        now.isoformat(),
    )


@router.delete("/meal/{meal_id}", dependencies=[Depends(verify_api_key)])
def delete_meal_route(meal_id: int):
    """Delete a meal event by ID."""
    deleted = delete_meal(meal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"deleted": meal_id, "status": "ok"}


@router.get("/status")
def status():
    """Health check endpoint."""
    return {
        "service": "bio-dashboard",
        "status": "ok",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "user": {
            "weight_kg": USER_WEIGHT_KG,
            "height_cm": USER_HEIGHT_CM,
            "age": USER_AGE,
            "fasting": USER_IS_FASTING,
        },
        "model": "allometric-cascade-v2+hydration",
    }


# ══════════════════════════════════════════════════════════════════════
# WATER TRACKING — Watch API + Dashboard endpoints
# ══════════════════════════════════════════════════════════════════════

def verify_watch_token(authorization: str = Header(default="")):
    """Verify Bearer token from watch (reuses BIO_API_KEY or WATER_WATCH_TOKEN)."""
    token = WATER_WATCH_TOKEN
    if not token:
        return  # No token configured, allow all
    expected = f"Bearer {token}"
    if authorization != expected:
        # Also accept x-api-key style
        if authorization != token:
            raise HTTPException(status_code=401, detail="Unauthorized")


def _get_effective_weight() -> float:
    """Get the latest weight from DB, fallback to config."""
    latest = get_latest_weight()
    if latest and latest.get("weight_kg"):
        return float(latest["weight_kg"])
    return USER_WEIGHT_KG


def _compute_today_goal() -> dict:
    """Compute today's dynamic water goal using all available data."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    weight = _get_effective_weight()

    # Check if Elvanse was taken today
    intakes = query_intakes(f"{today}T00:00:00", f"{today}T23:59:59")
    elvanse_active = any(i.get("substance") == "elvanse" for i in intakes)

    # Get steps from latest health snapshot
    latest_health = get_latest_health_snapshot()
    steps = 0
    if latest_health and latest_health.get("steps"):
        steps = int(latest_health["steps"])

    # Count caffeine doses
    caffeine_doses = sum(1 for i in intakes if i.get("substance") == "mate")

    goal_data = compute_daily_goal(
        weight_kg=weight,
        is_fasting=USER_IS_FASTING,
        elvanse_active=elvanse_active,
        steps=steps,
        caffeine_doses=caffeine_doses,
    )

    # Persist to DB
    upsert_water_goal(
        date=today,
        goal_ml=goal_data["goal_ml"],
        base_ml=goal_data["base_ml"],
        drug_mod_ml=goal_data["drug_modifier_ml"],
        fasting_mod_ml=goal_data["fasting_modifier_ml"],
        activity_mod_ml=goal_data["activity_modifier_ml"],
        weight_kg=weight,
        steps=steps,
    )

    return goal_data


# --- Watch endpoints (compatible with ServerService.ets) ---

from fastapi import Body, Request as FastAPIRequest


@router.post("/water/report")
async def water_report_endpoint(request: FastAPIRequest):
    """
    Receive hydration status from the Huawei Watch.
    POST /api/water/report
    Body: {device_id, current_intake, daily_goal, entry_count, last_drink_time, timestamp}
    """
    # Verify auth
    auth = request.headers.get("authorization", "")
    token = WATER_WATCH_TOKEN
    if token and auth != f"Bearer {token}" and auth != token:
        api_key = request.headers.get("x-api-key", "")
        if API_KEY and api_key != API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")

    data = await request.json()
    import logging
    log = logging.getLogger("bio.water")

    watch_intake = data.get("current_intake", 0)
    log.info(
        "Watch report: %d ml / %d ml (%d entries)",
        watch_intake,
        data.get("daily_goal", 0),
        data.get("entry_count", 0),
    )

    # Persist watch intake delta to DB so dashboard + velocity checks stay in sync
    if watch_intake > 0:
        db_total = get_todays_water_total()
        delta = watch_intake - db_total
        if delta > 0:
            insert_water_event(
                delta, "watch",
                f"auto-sync from {data.get('device_id', 'watch')}",
            )
            log.info("Persisted +%d ml delta (DB was %d, watch reports %d)", delta, db_total, watch_intake)

    return {"status": "ok"}


@router.get("/water/instruction")
async def water_instruction_endpoint(
    request: FastAPIRequest,
    current_intake: int = Query(default=0),
    daily_goal: int = Query(default=0),
    last_drink_time: str = Query(default=""),
):
    """
    Return a drinking instruction to the Huawei Watch.
    GET /api/water/instruction?current_intake=X&daily_goal=X&last_drink_time=X

    This is the core intelligence endpoint: computes dynamic goal,
    checks deficit, pacing, velocity, and returns coaching instructions.
    """
    # Verify auth
    auth = request.headers.get("authorization", "")
    token = WATER_WATCH_TOKEN
    if token and auth != f"Bearer {token}" and auth != token:
        api_key = request.headers.get("x-api-key", "")
        if API_KEY and api_key != API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")

    now = datetime.now()

    # Compute dynamic goal
    goal_data = _compute_today_goal()
    computed_goal = goal_data["goal_ml"]

    # Use watch's current_intake (it's the source of truth)
    intake = current_intake

    # Parse last drink time
    last_drink = None
    if last_drink_time:
        try:
            from dateutil.parser import parse as parse_date
            last_drink = parse_date(last_drink_time)
        except (ValueError, ImportError):
            try:
                last_drink = datetime.fromisoformat(last_drink_time.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Get hydration assessment
    assessment = assess_hydration(
        current_intake_ml=intake,
        goal_ml=computed_goal,
        now=now,
        last_drink_time=last_drink,
    )

    # Check intake velocity (overhydration protection)
    water_events = get_todays_water_events()
    velocity = check_intake_velocity(water_events, now)

    # Override with velocity alert if needed
    message = assessment["message"]
    priority = assessment["priority"]
    amount = assessment["recommended_amount"]
    deadline = assessment["deadline_minutes"]

    if velocity["alert"]:
        message = velocity["message"]
        priority = "critical"
        amount = 0  # Don't recommend more water!
        deadline = 0

    # daily_target_override: send the computed goal to the watch
    # (only if different from what the watch currently has)
    target_override = computed_goal if computed_goal != daily_goal else 0

    # Generate hydration curve with interval targets for the watch
    curve_data = generate_hydration_curve(
        current_intake_ml=intake,
        goal_ml=computed_goal,
        now=now,
    )

    return {
        "message": message,
        "recommended_amount": amount,
        "priority": priority,
        "deadline_minutes": deadline,
        "daily_target_override": target_override,
        "timestamp": now.isoformat(),
        "hydration_curve": curve_data,
    }


# --- Dashboard water endpoints ---

class WaterIntakeRequest(BaseModel):
    amount_ml: int = Field(..., ge=1, le=2000)
    source: str = Field(default="manual", pattern="^(watch|manual|ha)$")
    notes: str = ""
    timestamp: Optional[str] = None


@router.post("/water/intake", dependencies=[Depends(verify_api_key)])
def log_water_intake(req: WaterIntakeRequest):
    """Log a water intake event manually or from HA."""
    row_id = insert_water_event(req.amount_ml, req.source, req.notes, req.timestamp)

    # Check velocity after logging
    now = datetime.now()
    events = get_todays_water_events()
    velocity = check_intake_velocity(events, now)

    result = {"id": row_id, "amount_ml": req.amount_ml, "status": "ok"}
    if velocity["alert"]:
        result["warning"] = velocity
    return result


@router.get("/water/intake", dependencies=[Depends(verify_api_key)])
def get_water_intake(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: bool = False,
):
    """Query water intake events."""
    if today:
        return get_todays_water_events()
    if start and end:
        return query_water_events(start, end)
    now = datetime.now()
    return query_water_events(
        (now - timedelta(hours=24)).isoformat(),
        now.isoformat(),
    )


@router.delete("/water/intake/{event_id}", dependencies=[Depends(verify_api_key)])
def delete_water_intake(event_id: int):
    """Delete a water intake event."""
    deleted = delete_water_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Water event not found")
    return {"deleted": event_id, "status": "ok"}


@router.post("/water/reset", dependencies=[Depends(verify_api_key)])
def reset_water_today():
    """Delete all water events for today, resetting intake to 0."""
    count = reset_todays_water()
    return {"deleted_count": count, "status": "ok"}


@router.get("/water/goal", dependencies=[Depends(verify_api_key)])
def get_water_goal_endpoint(date: Optional[str] = None):
    """
    Get the computed daily water goal (with breakdown).
    If no date specified, computes for today.
    """
    if date:
        stored = get_water_goal(date)
        if stored:
            return stored
    # Compute fresh
    return _compute_today_goal()


@router.get("/water/goal/history", dependencies=[Depends(verify_api_key)])
def get_water_goal_history(days: int = Query(default=7, ge=1, le=90)):
    """Get water goal history for the last N days."""
    end = datetime.now()
    start = end - timedelta(days=days)
    return get_water_goals_range(
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )


@router.get("/water/status", dependencies=[Depends(verify_api_key)])
def water_status_endpoint():
    """
    Full hydration dashboard: goal, intake, assessment, velocity, dehydration.
    """
    now = datetime.now()
    goal_data = _compute_today_goal()
    total_ml = get_todays_water_total()
    events = get_todays_water_events()
    last_event = get_last_water_event()

    last_drink = None
    if last_event:
        try:
            last_drink = datetime.fromisoformat(last_event["timestamp"])
        except (ValueError, KeyError):
            pass

    assessment = assess_hydration(
        current_intake_ml=total_ml,
        goal_ml=goal_data["goal_ml"],
        now=now,
        last_drink_time=last_drink,
    )
    velocity = check_intake_velocity(events, now)

    # Dehydration detection from vitals
    latest_health = get_latest_health_snapshot()
    dehydration = {"alert": False}
    if latest_health:
        # Use today's morning baseline vs current
        dehydration = detect_dehydration_from_vitals(
            current_resting_hr=latest_health.get("resting_hr"),
            baseline_resting_hr=latest_health.get("resting_hr"),  # TODO: use morning baseline
            current_hrv=latest_health.get("hrv"),
            baseline_hrv=latest_health.get("hrv"),  # TODO: use overnight baseline
        )

    return {
        "timestamp": now.isoformat(),
        "goal": goal_data,
        "intake_ml": total_ml,
        "events_today": len(events),
        "assessment": assessment,
        "velocity": velocity,
        "dehydration": dehydration,
        "weight_kg": _get_effective_weight(),
    }


# --- Weight endpoints ---

class WeightRequest(BaseModel):
    weight_kg: float = Field(..., ge=30, le=300)
    source: str = Field(default="manual", pattern="^(manual|ha|watch)$")
    timestamp: Optional[str] = None


@router.post("/weight", dependencies=[Depends(verify_api_key)])
def log_weight(req: WeightRequest):
    """Log a weight measurement."""
    row_id = insert_weight(req.weight_kg, req.source, req.timestamp)
    return {"id": row_id, "weight_kg": req.weight_kg, "status": "ok"}


@router.get("/weight", dependencies=[Depends(verify_api_key)])
def get_weight(days: int = Query(default=30, ge=1, le=365)):
    """Get weight history."""
    end = datetime.now()
    start = end - timedelta(days=days)
    entries = query_weight_log(start.isoformat(), end.isoformat())
    latest = get_latest_weight()
    return {
        "latest": latest,
        "history": entries,
    }


@router.get("/weight/latest", dependencies=[Depends(verify_api_key)])
def get_weight_latest():
    """Get the most recent weight."""
    latest = get_latest_weight()
    if not latest:
        return {"found": False, "weight_kg": USER_WEIGHT_KG, "source": "config"}
    return {"found": True, **latest}


@router.get("/ddi-check", dependencies=[Depends(verify_api_key)])
def ddi_check():
    """
    Check current drug-drug interactions based on today's intakes.
    Returns active DDI warnings.
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    intakes = query_intakes(f"{today}T00:00:00", f"{today}T23:59:59")
    warnings = check_ddi_warnings(intakes, now, weight_kg=_get_effective_weight())
    return {
        "timestamp": now.isoformat(),
        "warnings": warnings,
        "warning_count": len(warnings),
    }


@router.get("/log-reminder", dependencies=[Depends(verify_api_key)])
def get_log_reminder():
    """
    Compute when the next subjective log is due.
    Schedule relative to Elvanse intake or fixed times.
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"

    intakes_today = query_intakes(today_start, today_end)
    logs_today = query_subjective_logs(today_start, today_end)

    logged_times = []
    for log in logs_today:
        try:
            logged_times.append(datetime.fromisoformat(log["timestamp"]))
        except (ValueError, KeyError):
            pass

    elvanse_intakes = [i for i in intakes_today if i.get("substance") == "elvanse"]

    if elvanse_intakes:
        elvanse_time = datetime.fromisoformat(elvanse_intakes[0]["timestamp"])
        target_times = [
            ("Baseline (vor Einnahme)", elvanse_time - timedelta(minutes=15)),
            ("+1.5h (Onset)", elvanse_time + timedelta(hours=1, minutes=30)),
            ("+4h (Peak)", elvanse_time + timedelta(hours=4)),
            ("+8h (Decline)", elvanse_time + timedelta(hours=8)),
            ("Vor Schlafen", now.replace(hour=22, minute=0, second=0)),
        ]
    else:
        target_times = [
            ("Morgens", now.replace(hour=9, minute=0, second=0)),
            ("Mittags", now.replace(hour=12, minute=0, second=0)),
            ("Nachmittags", now.replace(hour=15, minute=0, second=0)),
            ("Abends", now.replace(hour=18, minute=0, second=0)),
            ("Vor Schlafen", now.replace(hour=21, minute=0, second=0)),
        ]

    TOLERANCE_MIN = 30
    schedule = []
    next_due = None

    for label, target in target_times:
        already_logged = any(
            abs((lt - target).total_seconds()) < TOLERANCE_MIN * 60
            for lt in logged_times
        )
        if already_logged:
            entry_status = "done"
        elif target <= now + timedelta(minutes=TOLERANCE_MIN):
            entry_status = "due"
        else:
            entry_status = "upcoming"

        entry = {
            "label": label,
            "target_time": target.strftime("%H:%M"),
            "status": entry_status,
        }
        schedule.append(entry)

        if not already_logged and next_due is None and target >= now - timedelta(minutes=TOLERANCE_MIN):
            next_due = entry

    return {
        "schedule": schedule,
        "next_due": next_due,
        "logs_today": len(logs_today),
        "target_logs": 5,
    }


@router.get("/model/fit", dependencies=[Depends(verify_api_key)])
def get_model_fit():
    """
    Analyze Elvanse intake + focus rating pairs to estimate
    personal pharmacokinetic response curve.
    Requires at least 15 pairs for meaningful results.
    """
    import statistics

    now = datetime.now()
    start = (now - timedelta(days=90)).isoformat()
    end = now.isoformat()

    intakes = query_intakes(start, end)
    logs = query_subjective_logs(start, end)

    elvanse_intakes = [i for i in intakes if i.get("substance") == "elvanse"]

    if not elvanse_intakes or not logs:
        return {
            "status": "insufficient_data",
            "pairs": 0,
            "required": 15,
            "message": "Noch nicht genug Daten. Bitte regelmassig loggen.",
        }

    # Build pairs: for each focus log, find nearest preceding Elvanse intake
    pairs = []
    for log in logs:
        focus = log.get("focus")
        if focus is None:
            continue
        log_time = datetime.fromisoformat(log["timestamp"])

        best_intake = None
        best_offset = None
        for ei in elvanse_intakes:
            ei_time = datetime.fromisoformat(ei["timestamp"])
            offset_h = (log_time - ei_time).total_seconds() / 3600
            if 0 <= offset_h <= 16:
                if best_offset is None or offset_h < best_offset:
                    best_intake = ei
                    best_offset = offset_h

        if best_intake is not None:
            predicted_level = elvanse_effect_curve(best_offset, best_intake.get("dose_mg") or 40)
            pairs.append({
                "offset_h": round(best_offset, 2),
                "focus": focus,
                "predicted_level": round(predicted_level, 3),
                "dose_mg": best_intake.get("dose_mg"),
            })

    if len(pairs) < 15:
        return {
            "status": "insufficient_data",
            "pairs": len(pairs),
            "required": 15,
            "message": f"Noch {15 - len(pairs)} Paare noetig. Bitte 5x taeglich loggen.",
            "collected_pairs": pairs,
        }

    # Pearson correlation
    focus_values = [p["focus"] for p in pairs]
    level_values = [p["predicted_level"] for p in pairs]
    n = len(pairs)
    mean_f = statistics.mean(focus_values)
    mean_l = statistics.mean(level_values)
    std_f = statistics.stdev(focus_values) if n > 1 else 1.0
    std_l = statistics.stdev(level_values) if n > 1 else 1.0

    if std_f > 0 and std_l > 0:
        correlation = sum(
            (f - mean_f) * (l - mean_l) for f, l in zip(focus_values, level_values)
        ) / ((n - 1) * std_f * std_l)
    else:
        correlation = 0.0

    # Efficacy threshold (level where focus >= 7)
    high_focus_levels = [p["predicted_level"] for p in pairs if p["focus"] >= 7]
    threshold = min(high_focus_levels) if high_focus_levels else None

    # Personal tmax estimate
    offset_focus = {}
    for p in pairs:
        bucket = round(p["offset_h"])
        if bucket not in offset_focus:
            offset_focus[bucket] = []
        offset_focus[bucket].append(p["focus"])

    peak_offset = max(
        offset_focus.keys(),
        key=lambda k: statistics.mean(offset_focus[k])
    ) if offset_focus else None

    # Generate recommendation
    rec_parts = []
    if n < 30:
        rec_parts.append(f"Datenqualitaet: Maessig ({n} Paare). Mindestens 30 empfohlen.")
    else:
        rec_parts.append(f"Datenqualitaet: Gut ({n} Paare).")

    if correlation > 0.5:
        rec_parts.append(f"Starke Korrelation ({correlation:.2f}) zwischen Elvanse-Level und Fokus.")
    elif correlation > 0.2:
        rec_parts.append(f"Moderate Korrelation ({correlation:.2f}). Weiter loggen fuer bessere Praezision.")
    else:
        rec_parts.append(f"Schwache Korrelation ({correlation:.2f}). Andere Faktoren beeinflussen den Fokus stark.")

    if threshold is not None:
        rec_parts.append(f"Persoenliche Wirkschwelle: Fokus >= 7 ab Level {threshold:.2f}.")
    if peak_offset is not None:
        rec_parts.append(f"Dein persoenlicher Peak liegt bei ca. {peak_offset}h nach Einnahme.")

    return {
        "status": "ok",
        "pairs": n,
        "correlation": round(correlation, 3),
        "mean_focus": round(mean_f, 1),
        "mean_level": round(mean_l, 3),
        "personal_threshold": round(threshold, 3) if threshold else None,
        "personal_peak_offset_h": peak_offset,
        "high_focus_count": len(high_focus_levels),
        "recommendation": " | ".join(rec_parts),
        "collected_pairs": pairs,
    }
