"""
Bio-Engine: Bateman pharmacokinetic modeling for Elvanse (Lisdexamfetamine),
Medikinet IR (Methylphenidate IR), Medikinet retard (Methylphenidate MR),
and Caffeine (Lamate/Mate).

Mathematical Model:
  C(t) = (ka / (ka - ke)) * (e^(-ke*t) - e^(-ka*t))
  Normalized to [0, 1] by dividing by C(tmax).
  tmax = ln(ka/ke) / (ka - ke)

Sources:
  - Hutson et al., 2017, Frontiers in Pharmacology (Elvanse)
  - Kim et al., 2017, Pharmacometrics (Medikinet)
  - Markowitz et al., 2000, Clinical Pharmacokinetics (MPH t1/2)
  - Haessler et al., 2008, Int J Clin Pharmacol Ther (Medikinet retard fasted)
  - Kamimori et al., 2002, Int J Pharm (Caffeine)
  - Seng et al., 2009, J Clin Pharm Ther (Caffeine t1/2 non-smoker)

Bio-Score formula:
  base_score = circadian_rhythm(hour)      -- 0-60 points
  + elvanse_boost(t)                       -- 0-30 points
  + medikinet_boost(t)                     -- 0-25 points (IR + retard combined)
  + caffeine_boost(t)                      -- 0-15 points
  + sleep_modifier                         -- -20 to +10 points
  Clamped to [0, 100]
"""

import math
from datetime import datetime, timedelta
from typing import Optional

from app.config import (
    ELVANSE_DEFAULT_DOSE_MG,
    ELVANSE_KA,
    ELVANSE_KE,
    MEDIKINET_DEFAULT_DOSE_MG,
    MEDIKINET_IR_KA,
    MEDIKINET_IR_KE,
    MEDIKINET_RETARD_DEFAULT_DOSE_MG,
    MEDIKINET_RETARD_KA,
    MEDIKINET_RETARD_KE,
    MATE_CAFFEINE_MG,
    CAFFEINE_KA,
    CAFFEINE_KE,
)


# ── Bateman function core ─────────────────────────────────────────────

def _bateman_raw(t: float, ka: float, ke: float) -> float:
    """
    Un-normalized Bateman function at time t.
    C(t) = (ka / (ka - ke)) * (exp(-ke*t) - exp(-ka*t))
    Returns 0 for t < 0.
    """
    if t <= 0 or ka == ke:
        return 0.0
    return (ka / (ka - ke)) * (math.exp(-ke * t) - math.exp(-ka * t))


def _bateman_tmax(ka: float, ke: float) -> float:
    """Time of peak concentration: tmax = ln(ka/ke) / (ka - ke)."""
    if ka <= ke or ka <= 0 or ke <= 0:
        return 1.0  # fallback
    return math.log(ka / ke) / (ka - ke)


def _bateman_normalized(t: float, ka: float, ke: float) -> float:
    """
    Bateman function normalized to [0, 1].
    Peak is always 1.0, tail decays realistically.
    """
    if t <= 0:
        return 0.0
    tmax = _bateman_tmax(ka, ke)
    c_max = _bateman_raw(tmax, ka, ke)
    if c_max <= 0:
        return 0.0
    return max(0.0, _bateman_raw(t, ka, ke) / c_max)


# ── Substance effect curves ───────────────────────────────────────────

def elvanse_effect_curve(hours_since_intake: float, dose_mg: float = 40.0) -> float:
    """
    Elvanse (Lisdexamfetamine -> d-Amphetamine) Bateman curve.
    ka=0.78 h^-1 (prodrug hydrolysis rate), ke=0.088 h^-1 (d-amph elimination).
    Returns 0.0 - 1.0+ (normalized, dose-scaled).
    """
    dose_factor = dose_mg / ELVANSE_DEFAULT_DOSE_MG
    level = _bateman_normalized(hours_since_intake, ELVANSE_KA, ELVANSE_KE)
    return level * dose_factor


def medikinet_ir_effect_curve(hours_since_intake: float, dose_mg: float = 10.0) -> float:
    """
    Medikinet IR (Methylphenidate immediate release) Bateman curve.
    ka=1.72 h^-1 (fast absorption), ke=0.28 h^-1 (t1/2 ~2.5h).
    Returns 0.0 - 1.0+ (normalized, dose-scaled).
    """
    dose_factor = dose_mg / MEDIKINET_DEFAULT_DOSE_MG
    level = _bateman_normalized(hours_since_intake, MEDIKINET_IR_KA, MEDIKINET_IR_KE)
    return level * dose_factor


def medikinet_retard_effect_curve(hours_since_intake: float, dose_mg: float = 30.0) -> float:
    """
    Medikinet retard (Methylphenidate modified release) Bateman curve.
    FASTED state: single-peak (enteric coating dissolves prematurely).
    ka=1.2 h^-1 (widened absorption), ke=0.28 h^-1.
    Returns 0.0 - 1.0+ (normalized, dose-scaled).
    """
    dose_factor = dose_mg / MEDIKINET_RETARD_DEFAULT_DOSE_MG
    level = _bateman_normalized(hours_since_intake, MEDIKINET_RETARD_KA, MEDIKINET_RETARD_KE)
    return level * dose_factor


def caffeine_effect_curve(hours_since_intake: float, dose_mg: float = 76.0) -> float:
    """
    Caffeine (Lamate/Mate) Bateman curve.
    ka=2.5 h^-1, ke=0.16 h^-1 (non-smoker t1/2 ~4.3h).
    Linear superposition valid for <300mg.
    Returns 0.0 - 1.0+ (normalized, dose-scaled).
    """
    dose_factor = dose_mg / MATE_CAFFEINE_MG
    level = _bateman_normalized(hours_since_intake, CAFFEINE_KA, CAFFEINE_KE)
    return level * dose_factor


# ── Circadian base ────────────────────────────────────────────────────

def circadian_base_score(hour: float) -> float:
    """
    Base cognitive performance curve based on circadian rhythm.
    Returns 0-60 score.

    Peak: 09:00-12:00 and 15:00-17:00
    Trough: 13:00-14:30 (post-lunch dip) and 22:00-06:00 (night)
    """
    if hour < 6:
        return 15.0
    elif hour < 7:
        return 15.0 + (hour - 6) * 20.0
    elif hour < 9:
        return 35.0 + (hour - 7) * 12.5
    elif hour < 12:
        return 60.0
    elif hour < 13:
        return 60.0 - (hour - 12) * 10.0
    elif hour < 14.5:
        return 50.0 - (hour - 13) * 10.0
    elif hour < 15:
        return 35.0 + (hour - 14.5) * 30.0
    elif hour < 17:
        return 50.0
    elif hour < 20:
        return 50.0 - (hour - 17) * 8.0
    elif hour < 22:
        return 26.0 - (hour - 20) * 5.0
    else:
        return max(15.0, 16.0 - (hour - 22) * 0.5)


# ── Substance load aggregation ────────────────────────────────────────

def compute_substance_load(
    intakes: list[dict],
    target_time: datetime,
    substance: str,
    curve_fn,
    default_dose: float,
) -> float:
    """
    Sum effect of all intakes of a substance at a given time.
    Linear superposition: C_total(t) = sum(C_i(t - t_i)).
    """
    total = 0.0
    for intake in intakes:
        if intake.get("substance") != substance:
            continue
        intake_time = datetime.fromisoformat(intake["timestamp"])
        hours_since = (target_time - intake_time).total_seconds() / 3600.0
        dose = intake.get("dose_mg") or default_dose
        effect = curve_fn(hours_since, dose)
        if effect > 0.005:
            total += effect
    return total


def sleep_quality_modifier(sleep_duration_min: Optional[float],
                           sleep_confidence: Optional[float] = None) -> float:
    """
    Modifier based on last night's sleep. Returns -20 to +10.
    """
    if sleep_duration_min is None:
        return 0.0

    hours = sleep_duration_min / 60.0

    if hours < 5:
        base = -20.0
    elif hours < 6:
        base = -10.0
    elif hours < 7:
        base = -5.0
    elif hours < 8:
        base = 0.0
    elif hours < 9:
        base = 5.0
    else:
        base = 10.0

    if sleep_confidence is not None and sleep_confidence > 0:
        confidence_factor = sleep_confidence / 100.0
        base *= confidence_factor

    return base


# ── Bio-Score composite ───────────────────────────────────────────────

def compute_bio_score(
    target_time: datetime,
    intakes: list[dict],
    sleep_duration_min: Optional[float] = None,
    sleep_confidence: Optional[float] = None,
) -> dict:
    """
    Compute composite Bio-Score at a given time using Bateman PK curves.

    Returns dict with score, component boosts, raw levels, and phase.
    """
    hour = target_time.hour + target_time.minute / 60.0

    # 1. Circadian base (0-60)
    circadian = circadian_base_score(hour)

    # 2. Elvanse boost (0-30)
    elvanse_level = compute_substance_load(
        intakes, target_time, "elvanse",
        elvanse_effect_curve, ELVANSE_DEFAULT_DOSE_MG
    )
    elvanse_boost = min(30.0, elvanse_level * 30.0)

    # 3. Medikinet boost: IR + retard combined (0-25)
    medikinet_ir_level = compute_substance_load(
        intakes, target_time, "medikinet",
        medikinet_ir_effect_curve, MEDIKINET_DEFAULT_DOSE_MG
    )
    medikinet_retard_level = compute_substance_load(
        intakes, target_time, "medikinet_retard",
        medikinet_retard_effect_curve, MEDIKINET_RETARD_DEFAULT_DOSE_MG
    )
    medikinet_combined = medikinet_ir_level + medikinet_retard_level
    medikinet_boost = min(25.0, medikinet_combined * 25.0)

    # 4. Caffeine boost (0-15)
    caffeine_level = compute_substance_load(
        intakes, target_time, "mate",
        caffeine_effect_curve, MATE_CAFFEINE_MG
    )
    caffeine_boost = min(15.0, caffeine_level * 15.0)

    # 5. Sleep modifier (-20 to +10)
    sleep_mod = sleep_quality_modifier(sleep_duration_min, sleep_confidence)

    # Composite
    raw_score = circadian + elvanse_boost + medikinet_boost + caffeine_boost + sleep_mod
    score = max(0.0, min(100.0, raw_score))

    # CNS stimulant load (sum of all normalized levels, for safety display)
    cns_load = elvanse_level + medikinet_combined + caffeine_level

    # Determine phase
    stim_level = max(elvanse_level, medikinet_combined)
    phase = _determine_phase(stim_level, caffeine_level, hour)

    return {
        "score": round(score, 1),
        "circadian": round(circadian, 1),
        "elvanse_boost": round(elvanse_boost, 1),
        "medikinet_boost": round(medikinet_boost, 1),
        "caffeine_boost": round(caffeine_boost, 1),
        "sleep_modifier": round(sleep_mod, 1),
        "elvanse_level": round(elvanse_level, 3),
        "medikinet_level": round(medikinet_combined, 3),
        "caffeine_level": round(caffeine_level, 3),
        "cns_load": round(cns_load, 3),
        "phase": phase,
        "timestamp": target_time.isoformat(),
    }


def _determine_phase(stim_level: float, caffeine_level: float, hour: float) -> str:
    """Determine current bio phase as human-readable string."""
    if hour < 6:
        return "sleep"
    if hour < 7:
        return "waking"

    if stim_level >= 0.85:
        return "peak-focus"
    elif stim_level >= 0.5:
        return "active-focus"
    elif stim_level >= 0.2:
        return "declining"
    elif stim_level >= 0.05:
        return "low-residual"

    if 12.5 <= hour <= 14.5:
        return "midday-dip"
    if hour >= 20:
        return "wind-down"

    return "baseline"


def generate_day_curve(
    date: datetime,
    intakes: list[dict],
    sleep_duration_min: Optional[float] = None,
    sleep_confidence: Optional[float] = None,
    interval_minutes: int = 15,
) -> list[dict]:
    """
    Generate Bio-Score data points for a full day at given interval.
    """
    points = []
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(0, 24 * 60, interval_minutes):
        t = start + timedelta(minutes=i)
        point = compute_bio_score(t, intakes, sleep_duration_min, sleep_confidence)
        points.append(point)

    return points
