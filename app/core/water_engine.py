"""
Water Engine: Evidence-based dynamic hydration model.

Computes personalised daily water goals and generates real-time
drinking instructions for the Huawei Watch water tracker integration.

Scientific basis (Gemini deep-research output):
  - Baseline: Holliday-Segar / weight-based 30-35 ml/kg (EFSA 2010, IOM 2004)
  - Amphetamine modifier: +110 ml for 5% REE increase (Elvanse PD)
  - Fasting modifier: +500 ml (OMAD food-moisture deficit)
  - Activity modifier: +60 ml per 1,000 steps above 4,000 sedentary baseline
  - Caffeine: 1:1 BHI for habitual consumers (Maughan & Griffin 2003)
  - Renal excretion cap: 800 ml/h max (safety buffer below 900 ml/h)
  - Dehydration telemetry: HR drift ≥4 bpm + HRV drop → alert
  - Pacing: ~250-300 ml/h over waking hours, front/back-loaded for fasting

GI absorption kinetics (Section 3 of research):
  - Gastric half-emptying: 13 ± 1 min for plain water
  - Peak intestinal absorption: ~20 min post-ingestion
  - Max renal clearance: 900-1,000 ml/h → hard cap at 800 ml/h

Sources:
  EFSA (2010), IOM/NAM (2004), Holliday & Segar (1957),
  Chidester & Spangler (1997), Maughan & Griffin (2003),
  Killer et al. (2014), Kamimori et al. (2002)
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import (
    USER_WEIGHT_KG,
    USER_IS_FASTING,
    WATER_BASE_ML_PER_KG,
    WATER_DRUG_MODIFIER_ML,
    WATER_ACTIVITY_ML_PER_1K_STEPS,
    WATER_ACTIVITY_BASELINE_STEPS,
    WATER_FASTING_MODIFIER_ML,
    WATER_MAX_HOURLY_ML,
    WATER_WAKING_HOURS,
    WATER_DEFAULT_GOAL_ML,
    DEHYDRATION_HR_DRIFT_BPM,
    DEHYDRATION_HRV_DROP_PCT,
)


# ── Dynamic daily goal ───────────────────────────────────────────────

def compute_daily_goal(
    weight_kg: float = USER_WEIGHT_KG,
    is_fasting: bool = USER_IS_FASTING,
    elvanse_active: bool = False,
    steps: int = 0,
    caffeine_doses: int = 0,
) -> dict:
    """
    Compute the personalised Total Daily Water (TDW) target.

    Formula (from Gemini evidence-based model):
      TDW = base + drug_mod + fasting_mod + activity_mod
      base        = weight_kg × 33.3 ml/kg
      drug_mod    = +110 ml   (if Elvanse taken today)
      fasting_mod = +500 ml   (if OMAD / skipping meals)
      activity_mod = 60 × max(0, (steps - 4000) / 1000)

    Caffeine (Mate) is counted 1:1 — no penalty for habitual users.

    Returns dict with goal_ml and breakdown of each modifier.
    """
    # Base requirement (weight-scaled)
    base_ml = weight_kg * WATER_BASE_ML_PER_KG

    # Pharmacological modifier: Elvanse sympathomimetic REE increase
    drug_mod = WATER_DRUG_MODIFIER_ML if elvanse_active else 0

    # Chrononutritional modifier: OMAD food moisture deficit
    fasting_mod = WATER_FASTING_MODIFIER_ML if is_fasting else 0

    # Kinematic modifier: activity above sedentary baseline
    step_surplus = max(0, steps - WATER_ACTIVITY_BASELINE_STEPS)
    activity_mod = int(WATER_ACTIVITY_ML_PER_1K_STEPS * (step_surplus / 1000.0))

    # Total
    goal_ml = int(base_ml + drug_mod + fasting_mod + activity_mod)

    return {
        "goal_ml": goal_ml,
        "base_ml": int(base_ml),
        "drug_modifier_ml": drug_mod,
        "fasting_modifier_ml": fasting_mod,
        "activity_modifier_ml": activity_mod,
        "weight_kg": weight_kg,
        "is_fasting": is_fasting,
        "elvanse_active": elvanse_active,
        "steps": steps,
    }


# ── Expected intake schedule ─────────────────────────────────────────

def expected_intake_at_hour(
    hour: float,
    goal_ml: int,
    wake_hour: float = 7.0,
    sleep_hour: float = 23.0,
    is_fasting: bool = USER_IS_FASTING,
) -> float:
    """
    Expected cumulative intake at a given hour of day.

    For fasting users: front-load morning (07-12) and back-load evening
    (18-23) to compensate for missing breakfast/dinner moisture.
    For non-fasting: roughly linear over waking hours.

    Returns expected_ml at the given hour.
    """
    if hour <= wake_hour:
        return 0.0
    if hour >= sleep_hour:
        return float(goal_ml)

    waking_total = sleep_hour - wake_hour
    elapsed = hour - wake_hour
    progress = elapsed / waking_total

    if is_fasting:
        # Linear pacing — simple and predictable.
        # OMAD fasting compensation is already in the goal_ml total (+500 ml),
        # so no need for a complex S-curve shape.
        return goal_ml * progress
    else:
        return goal_ml * progress


# ── Hydration status assessment ──────────────────────────────────────

def assess_hydration(
    current_intake_ml: int,
    goal_ml: int,
    now: Optional[datetime] = None,
    last_drink_time: Optional[datetime] = None,
    wake_hour: float = 7.0,
    sleep_hour: float = 23.0,
    is_fasting: bool = USER_IS_FASTING,
) -> dict:
    """
    Assess current hydration status and generate a coaching instruction.

    Returns:
      message: str  — text for watch display (German)
      recommended_amount: int — ml to drink now
      priority: str — none/low/normal/high/critical
      deadline_minutes: int
      deficit_ml: int  — how far behind schedule
      pacing_ml_per_hour: int
      status: str — on_track / behind / critical / overhydrated / goal_reached
    """
    if now is None:
        now = datetime.now()

    hour = now.hour + now.minute / 60.0
    expected = expected_intake_at_hour(hour, goal_ml, wake_hour, sleep_hour, is_fasting)
    deficit = int(expected - current_intake_ml)
    pct = (current_intake_ml / goal_ml * 100) if goal_ml > 0 else 0

    # Remaining hours in the day
    remaining_hours = max(0.5, sleep_hour - hour)
    remaining_ml = max(0, goal_ml - current_intake_ml)
    pacing = int(remaining_ml / remaining_hours) if remaining_hours > 0 else 0

    message = ""
    amount = 0
    priority = "none"
    deadline = 0
    status = "on_track"

    # 1. Goal already reached
    if current_intake_ml >= goal_ml:
        status = "goal_reached"
        message = ""
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 2. Critical deficit (>1000ml behind schedule)
    if deficit > 1000:
        amount = min(500, deficit)
        message = f"Stark im Rückstand ({deficit} ml)! Trink jetzt {amount} ml."
        priority = "critical"
        deadline = 20
        status = "critical"
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 3. Significant deficit (>500ml behind)
    if deficit > 500:
        amount = min(400, deficit)
        message = f"Du bist {deficit} ml im Rückstand. Trink {amount} ml!"
        priority = "high"
        deadline = 30
        status = "behind"
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 4. Moderate deficit (>200ml behind)
    if deficit > 200:
        amount = min(300, deficit)
        message = f"Etwas im Rückstand ({deficit} ml). Trink {amount} ml."
        priority = "normal"
        deadline = 45
        status = "behind"
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 5. Long time since last drink (>120 min)
    if last_drink_time is not None:
        # ensure both are naive or both are aware
        if last_drink_time.tzinfo is not None and now.tzinfo is None:
            now_cmp = now.replace(tzinfo=timezone.utc)
        elif last_drink_time.tzinfo is None and now.tzinfo is not None:
            now_cmp = now.replace(tzinfo=None)
        else:
            now_cmp = now
        minutes_since = (now_cmp - last_drink_time).total_seconds() / 60.0
        if minutes_since > 120:
            message = "Über 2 Stunden ohne Wasser — trink etwas!"
            amount = 250
            priority = "high"
            deadline = 15
            status = "behind"
            return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)
        elif minutes_since > 90:
            message = "90 Min seit dem letzten Trinken. Trink 200 ml."
            amount = 200
            priority = "normal"
            deadline = 30
            status = "behind"
            return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 6. No drinks at all today, but morning has started
    if current_intake_ml == 0 and hour > wake_hour + 1:
        message = "Noch nichts getrunken heute — starte jetzt!"
        amount = 250
        priority = "high"
        deadline = 15
        status = "critical"
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    # 7. On track — gentle pacing reminder
    if pacing > 0 and deficit > 0:
        message = f"Gut dabei! Nächstes Glas: {min(250, pacing)} ml."
        amount = min(250, pacing)
        priority = "low"
        deadline = 60
        status = "on_track"
        return _build_result(message, amount, priority, deadline, deficit, pacing, status, pct)

    return _build_result("", 0, "none", 0, deficit, pacing, "on_track", pct)


def _build_result(
    message: str, amount: int, priority: str, deadline: int,
    deficit: int, pacing: int, status: str, pct: float,
) -> dict:
    return {
        "message": message,
        "recommended_amount": amount,
        "priority": priority,
        "deadline_minutes": deadline,
        "deficit_ml": deficit,
        "pacing_ml_per_hour": pacing,
        "status": status,
        "progress_pct": round(pct, 1),
    }


# ── Intake velocity check (overhydration protection) ─────────────────

def check_intake_velocity(
    water_events: list[dict],
    now: Optional[datetime] = None,
) -> dict:
    """
    Check if intake velocity exceeds the safe renal excretion limit.

    Research (Section 3):
      Max renal clearance: 900-1000 ml/h
      Safety cap: 800 ml/h (hard limit)
      Gastric half-emptying: 13 min, peak absorption: 20 min

    Returns alert info if velocity exceeded.
    """
    if now is None:
        now = datetime.now()

    # Sum water intake in the last 60 minutes
    one_hour_ago = now - timedelta(hours=1)
    recent_ml = 0
    for ev in water_events:
        ts = ev.get("timestamp", "")
        try:
            ev_time = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            continue
        if ev_time >= one_hour_ago and ev_time <= now:
            recent_ml += ev.get("amount_ml", 0)

    alert = recent_ml > WATER_MAX_HOURLY_ML
    return {
        "last_60min_ml": recent_ml,
        "max_hourly_ml": WATER_MAX_HOURLY_ML,
        "alert": alert,
        "message": (
            f"ACHTUNG: {recent_ml} ml in 60 Min! Max {WATER_MAX_HOURLY_ML} ml/h "
            "um Hyponatriämie zu vermeiden. Trinkpause einlegen!"
        ) if alert else "",
    }


# ── Dehydration detection from wearable telemetry ────────────────────

def detect_dehydration_from_vitals(
    current_resting_hr: Optional[float],
    baseline_resting_hr: Optional[float],
    current_hrv: Optional[float],
    baseline_hrv: Optional[float],
) -> dict:
    """
    Detect dehydration from HR drift + HRV suppression.

    Research (Section 9):
      - Mild dehydration (1-2% body mass loss) causes:
        - HR increase of 3-5 bpm per 1% body mass loss
        - Significant HRV (RMSSD) suppression
      - Threshold: resting HR drift ≥4 bpm + HRV drop ≥15%

    Returns alert dict.
    """
    if current_resting_hr is None or baseline_resting_hr is None:
        return {"alert": False, "message": ""}

    hr_drift = current_resting_hr - baseline_resting_hr

    hrv_drop_pct = 0.0
    if current_hrv is not None and baseline_hrv is not None and baseline_hrv > 0:
        hrv_drop_pct = ((baseline_hrv - current_hrv) / baseline_hrv) * 100.0

    alert = hr_drift >= DEHYDRATION_HR_DRIFT_BPM and hrv_drop_pct >= DEHYDRATION_HRV_DROP_PCT

    message = ""
    if alert:
        message = (
            f"Dehydrierung erkannt! Ruhepuls +{hr_drift:.0f} bpm, "
            f"HRV -{hrv_drop_pct:.0f}%. Sofort 500 ml trinken!"
        )

    return {
        "alert": alert,
        "hr_drift_bpm": round(hr_drift, 1),
        "hrv_drop_pct": round(hrv_drop_pct, 1),
        "message": message,
        "estimated_body_mass_loss_pct": round(hr_drift / 4.0, 1) if hr_drift > 0 else 0.0,
    }


# ── Hydration Bio-Score modifier ─────────────────────────────────────

def hydration_bio_score_modifier(
    current_intake_ml: int,
    goal_ml: int,
    hour: float,
    wake_hour: float = 7.0,
    sleep_hour: float = 23.0,
    is_fasting: bool = USER_IS_FASTING,
) -> float:
    """
    Compute a Bio-Score modifier based on hydration status.

    Returns a score between -10 and +5:
      +5  = well hydrated (ahead of schedule)
       0  = on track
      -5  = moderately behind
      -10 = severely dehydrated / critical deficit

    Rationale:
      Dehydration impairs cognitive performance (Section 8,9):
      - 1% body mass loss → measurable cognitive decline
      - Migraine trigger risk increases
    """
    if goal_ml <= 0:
        return 0.0

    expected = expected_intake_at_hour(hour, goal_ml, wake_hour, sleep_hour, is_fasting)
    if expected <= 0:
        return 0.0

    ratio = current_intake_ml / expected

    if ratio >= 1.1:
        return 5.0
    elif ratio >= 0.95:
        return 3.0
    elif ratio >= 0.8:
        return 0.0
    elif ratio >= 0.6:
        return -5.0
    elif ratio >= 0.4:
        return -8.0
    else:
        return -10.0


# ── Hydration curve for watch display ─────────────────────────────────

def generate_hydration_curve(
    current_intake_ml: int,
    goal_ml: int,
    now: Optional[datetime] = None,
    wake_hour: float = 7.0,
    sleep_hour: float = 23.0,
    is_fasting: bool = USER_IS_FASTING,
) -> dict:
    """
    Generate hydration curve data for the Huawei Watch display.

    Returns a dict with:
      - expected_curve: list of {hour, ml} points (every 30 min, wake→sleep)
      - targets: 15/30/45/60 min forward micro-goals with delta_ml
      - current_ml / goal_ml / current_hour for rendering context

    The curve allows the watch to draw:
      1. The expected intake line (dashed) — the ideal pace
      2. Actual intake level vs time (solid fill)
      3. Target dots at 15/30/45/60 min intervals ahead

    GI absorption kinetics inform the target spacing:
      - Gastric half-emptying: 13 ± 1 min → 15 min as minimum pacing unit
      - Peak intestinal absorption: ~20 min → 30 min for first meaningful target
      - 45 min + 60 min for mid-range and hourly micro-goals
    """
    if now is None:
        now = datetime.now()

    current_hour = now.hour + now.minute / 60.0

    # Generate expected curve points (every 30 min from wake to sleep)
    expected_curve: list[dict] = []
    steps = int((sleep_hour - wake_hour) / 0.5) + 1
    for i in range(steps):
        h = wake_hour + i * 0.5
        if h > sleep_hour:
            h = sleep_hour
        expected_ml = expected_intake_at_hour(h, goal_ml, wake_hour, sleep_hour, is_fasting)
        expected_curve.append({"hour": round(h, 2), "ml": int(expected_ml)})

    # Current expected value
    current_expected = int(expected_intake_at_hour(
        current_hour, goal_ml, wake_hour, sleep_hour, is_fasting
    ))

    # Compute interval targets (15, 30, 45, 60 min ahead)
    targets: list[dict] = []
    for minutes in [15, 30, 45, 60]:
        target_hour = current_hour + minutes / 60.0
        if target_hour > sleep_hour:
            target_hour = sleep_hour
        target_ml = int(expected_intake_at_hour(
            target_hour, goal_ml, wake_hour, sleep_hour, is_fasting
        ))
        delta_ml = max(0, target_ml - current_intake_ml)
        label = f"{minutes}'" if minutes < 60 else "1h"
        targets.append({
            "minutes": minutes,
            "target_ml": target_ml,
            "delta_ml": delta_ml,
            "label": label,
        })

    return {
        "current_ml": current_intake_ml,
        "goal_ml": goal_ml,
        "current_hour": round(current_hour, 2),
        "current_expected_ml": current_expected,
        "wake_hour": wake_hour,
        "sleep_hour": sleep_hour,
        "targets": targets,
        "expected_curve": expected_curve,
    }
