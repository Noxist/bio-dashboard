"""
Bio-Engine v2: Advanced pharmacokinetic modeling with allometric scaling,
three-stage Elvanse cascade model, DDI warnings, and HRV-based Bio-Score.

Substances modeled:
  - Elvanse (Lisdexamfetamine -> d-Amphetamine):
      Three-stage cascade: GI absorption (PEPT1) -> erythrocyte hydrolysis -> elimination
      A(t) = F*D*k1*k2 * sum_i[e^(-ri*t) / prod_j!=i(rj - ri)]

  - Medikinet IR (Methylphenidate immediate release): Bateman function
  - Medikinet retard (Methylphenidate MR, FASTED): Collapsed single-peak Bateman
  - Caffeine (Mate): Bateman with linear superposition (Heaviside)
  - Co-Dafalgan (Paracetamol 500mg + Codein 30mg): Bateman + DDI logic

Allometric scaling (96 kg -> 70 kg reference):
  Cmax_user = Cmax_ref * (70 / weight_user)     -- Vd proportional to weight^1.0
  CL_user = CL_pop * (weight / 70)^0.75         -- Clearance allometric exponent

Bio-Score: 0-100 composite:
  circadian_rhythm(hour)    -- 0-60 pts
  + elvanse_boost(t)        -- 0-30 pts
  + medikinet_boost(t)      -- 0-25 pts (IR + retard)
  + caffeine_boost(t)       -- 0-15 pts
  + sleep_modifier          -- -20 to +10 pts
  + hrv_penalty             -- 0 to -15 pts
  Clamped to [0, 100]

Sources:
  - Hutson et al., 2017 / Ermer et al., 2016 (Elvanse/LDX)
  - Kim et al., 2017, Markowitz et al., 2000 (Methylphenidate)
  - Haessler et al., 2008 (Medikinet retard fasted)
  - Kamimori et al., 2002, Seng et al., 2009 (Caffeine)
"""

import math
from datetime import datetime, timedelta
from typing import Optional

from app.config import (
    ELVANSE_DEFAULT_DOSE_MG,
    ELVANSE_KA,
    ELVANSE_KA_ABS,
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
    CO_DAFALGAN_DEFAULT_DOSE_MG,
    CO_DAFALGAN_CODEIN_KA,
    CO_DAFALGAN_CODEIN_KE,
    CO_DAFALGAN_PARACETAMOL_KA,
    CO_DAFALGAN_PARACETAMOL_KE,
    CODEIN_RATIO,
    PARACETAMOL_MAX_DAILY_FASTING_MG,
    CMAX_REF,
    REFERENCE_WEIGHT_KG,
    USER_WEIGHT_KG,
    USER_IS_FASTING,
)


# ── Allometric scaling ───────────────────────────────────────────────

def allometric_cmax(cmax_ref: float, weight_user: float) -> float:
    """
    Scale reference Cmax allometrically for user weight.
    Cmax is proportional to 1/Vd, and Vd proportional to weight^1.0
    -> Cmax_user = Cmax_ref * (ref_weight / user_weight)
    """
    if weight_user <= 0:
        return cmax_ref
    return cmax_ref * (REFERENCE_WEIGHT_KG / weight_user)


# ── Bateman function core (for Medikinet, Caffeine, Co-Dafalgan) ─────

def _bateman_raw(t: float, ka: float, ke: float) -> float:
    """
    Un-normalized Bateman function.
    C(t) = (ka / (ka - ke)) * (exp(-ke*t) - exp(-ka*t))
    """
    if t <= 0 or ka == ke:
        return 0.0
    return (ka / (ka - ke)) * (math.exp(-ke * t) - math.exp(-ka * t))


def _bateman_tmax(ka: float, ke: float) -> float:
    """Time of peak: tmax = ln(ka/ke) / (ka - ke)."""
    if ka <= ke or ka <= 0 or ke <= 0:
        return 1.0
    return math.log(ka / ke) / (ka - ke)


def _bateman_normalized(t: float, ka: float, ke: float) -> float:
    """Bateman function normalized so peak = 1.0."""
    if t <= 0:
        return 0.0
    tmax = _bateman_tmax(ka, ke)
    c_max = _bateman_raw(tmax, ka, ke)
    if c_max <= 0:
        return 0.0
    return max(0.0, _bateman_raw(t, ka, ke) / c_max)


# ── Three-stage cascade model (Elvanse) ──────────────────────────────
#
# Linked compartment model for Lisdexamfetamine:
#   Gut --[k_abs]--> LDX_plasma --[k_hyd]--> d-Amph_plasma --[k_e]--> eliminated
#
# Analytical solution for d-Amphetamine amount A(t):
#   A(t) = G0 * k_abs * k_hyd * SUM_i [ e^(-r_i*t) / PROD_{j!=i}(r_j - r_i) ]
#   where r = [k_abs, k_hyd, k_e] and G0 = F * Dose
#

def _cascade_raw(t: float, k_abs: float, k_hyd: float, k_e: float) -> float:
    """
    Three-compartment cascade analytical solution (un-normalized).
    Returns the shape function value at time t.
    """
    if t <= 0:
        return 0.0
    rates = [k_abs, k_hyd, k_e]
    result = 0.0
    for i in range(3):
        ri = rates[i]
        denom = 1.0
        for j in range(3):
            if j != i:
                denom *= (rates[j] - ri)
        if abs(denom) < 1e-12:
            continue
        result += math.exp(-ri * t) / denom
    return k_abs * k_hyd * result


# Cache for cascade peak values (computed once per rate constant set)
_CASCADE_PEAK_CACHE: dict[tuple, float] = {}


def _cascade_peak(k_abs: float, k_hyd: float, k_e: float) -> float:
    """Find peak of cascade function numerically. Cached."""
    key = (round(k_abs, 6), round(k_hyd, 6), round(k_e, 6))
    if key in _CASCADE_PEAK_CACHE:
        return _CASCADE_PEAK_CACHE[key]
    peak = 0.0
    for i in range(1, 3001):  # 0.01h to 30h
        t = i * 0.01
        val = _cascade_raw(t, k_abs, k_hyd, k_e)
        if val > peak:
            peak = val
    _CASCADE_PEAK_CACHE[key] = peak
    return peak


def _cascade_normalized(t: float, k_abs: float, k_hyd: float, k_e: float) -> float:
    """Cascade function normalized so peak = 1.0."""
    if t <= 0:
        return 0.0
    peak = _cascade_peak(k_abs, k_hyd, k_e)
    if peak <= 0:
        return 0.0
    return max(0.0, _cascade_raw(t, k_abs, k_hyd, k_e) / peak)


# ── Concentration calculators (absolute ng/ml) ───────────────────────

def elvanse_concentration(hours: float, dose_mg: float = 40.0,
                          weight_kg: float = USER_WEIGHT_KG) -> float:
    """
    d-Amphetamine plasma concentration from Elvanse (ng/ml).
    Three-stage cascade model with allometric Cmax scaling.
    """
    cmax = allometric_cmax(CMAX_REF["elvanse"], weight_kg)
    dose_factor = dose_mg / ELVANSE_DEFAULT_DOSE_MG
    level = _cascade_normalized(hours, ELVANSE_KA_ABS, ELVANSE_KA, ELVANSE_KE)
    return cmax * dose_factor * level


def medikinet_ir_concentration(hours: float, dose_mg: float = 10.0,
                               weight_kg: float = USER_WEIGHT_KG) -> float:
    """Methylphenidate IR plasma concentration (ng/ml)."""
    cmax = allometric_cmax(CMAX_REF["medikinet_ir"], weight_kg)
    dose_factor = dose_mg / MEDIKINET_DEFAULT_DOSE_MG
    level = _bateman_normalized(hours, MEDIKINET_IR_KA, MEDIKINET_IR_KE)
    return cmax * dose_factor * level


def medikinet_retard_concentration(hours: float, dose_mg: float = 30.0,
                                   weight_kg: float = USER_WEIGHT_KG) -> float:
    """Methylphenidate MR concentration (ng/ml). FASTED: collapsed single peak."""
    cmax = allometric_cmax(CMAX_REF["medikinet_retard"], weight_kg)
    dose_factor = dose_mg / MEDIKINET_RETARD_DEFAULT_DOSE_MG
    level = _bateman_normalized(hours, MEDIKINET_RETARD_KA, MEDIKINET_RETARD_KE)
    return cmax * dose_factor * level


def caffeine_concentration(hours: float, dose_mg: float = 76.0,
                           weight_kg: float = USER_WEIGHT_KG) -> float:
    """Caffeine plasma concentration (ng/ml)."""
    cmax = allometric_cmax(CMAX_REF["caffeine"], weight_kg)
    dose_factor = dose_mg / MATE_CAFFEINE_MG
    level = _bateman_normalized(hours, CAFFEINE_KA, CAFFEINE_KE)
    return cmax * dose_factor * level


def codein_concentration(hours: float, dose_paracetamol_mg: float = 500.0,
                         weight_kg: float = USER_WEIGHT_KG) -> float:
    """Codein plasma concentration from Co-Dafalgan (ng/ml)."""
    codein_dose = dose_paracetamol_mg * CODEIN_RATIO
    cmax = allometric_cmax(CMAX_REF["codein"], weight_kg)
    dose_factor = codein_dose / 30.0  # reference: 30mg codein
    level = _bateman_normalized(hours, CO_DAFALGAN_CODEIN_KA, CO_DAFALGAN_CODEIN_KE)
    return cmax * dose_factor * level


def paracetamol_concentration(hours: float, dose_mg: float = 500.0,
                              weight_kg: float = USER_WEIGHT_KG) -> float:
    """Paracetamol plasma concentration from Co-Dafalgan (ng/ml)."""
    cmax = allometric_cmax(CMAX_REF["paracetamol"], weight_kg)
    dose_factor = dose_mg / 500.0  # reference: 500mg paracetamol
    level = _bateman_normalized(hours, CO_DAFALGAN_PARACETAMOL_KA, CO_DAFALGAN_PARACETAMOL_KE)
    return cmax * dose_factor * level


# ── Relative level calculators (0-1 at standard dose peak) ───────────
# Used for Bio-Score computation.

def elvanse_level(hours: float, dose_mg: float = 40.0) -> float:
    """Relative d-Amph level (0-1 at standard dose peak). Three-stage cascade shape."""
    dose_factor = dose_mg / ELVANSE_DEFAULT_DOSE_MG
    return _cascade_normalized(hours, ELVANSE_KA_ABS, ELVANSE_KA, ELVANSE_KE) * dose_factor


def medikinet_ir_level(hours: float, dose_mg: float = 10.0) -> float:
    """Relative MPH IR level (0-1 at standard dose peak)."""
    dose_factor = dose_mg / MEDIKINET_DEFAULT_DOSE_MG
    return _bateman_normalized(hours, MEDIKINET_IR_KA, MEDIKINET_IR_KE) * dose_factor


def medikinet_retard_level(hours: float, dose_mg: float = 30.0) -> float:
    """Relative MPH retard level (0-1, FASTED collapsed profile)."""
    dose_factor = dose_mg / MEDIKINET_RETARD_DEFAULT_DOSE_MG
    return _bateman_normalized(hours, MEDIKINET_RETARD_KA, MEDIKINET_RETARD_KE) * dose_factor


def caffeine_level(hours: float, dose_mg: float = 76.0) -> float:
    """Relative caffeine level (0-1 at standard dose peak)."""
    dose_factor = dose_mg / MATE_CAFFEINE_MG
    return _bateman_normalized(hours, CAFFEINE_KA, CAFFEINE_KE) * dose_factor


def codein_level(hours: float, dose_paracetamol_mg: float = 500.0) -> float:
    """Relative codein level (0-1 at standard dose peak)."""
    codein_dose = dose_paracetamol_mg * CODEIN_RATIO
    dose_factor = codein_dose / 30.0
    return _bateman_normalized(hours, CO_DAFALGAN_CODEIN_KA, CO_DAFALGAN_CODEIN_KE) * dose_factor


# ── Legacy-compatible effect curves (for model/fit backward compat) ──

def elvanse_effect_curve(hours_since_intake: float, dose_mg: float = 40.0) -> float:
    """Legacy-compatible: returns relative level via three-stage cascade."""
    return elvanse_level(hours_since_intake, dose_mg)


def medikinet_ir_effect_curve(hours_since_intake: float, dose_mg: float = 10.0) -> float:
    return medikinet_ir_level(hours_since_intake, dose_mg)


def medikinet_retard_effect_curve(hours_since_intake: float, dose_mg: float = 30.0) -> float:
    return medikinet_retard_level(hours_since_intake, dose_mg)


def caffeine_effect_curve(hours_since_intake: float, dose_mg: float = 76.0) -> float:
    return caffeine_level(hours_since_intake, dose_mg)


# ── Circadian base ───────────────────────────────────────────────────

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


# ── Substance load aggregation (Heaviside superposition) ─────────────

def compute_substance_load_ngml(
    intakes: list[dict],
    target_time: datetime,
    substance: str,
    conc_fn,
    default_dose: float,
) -> float:
    """
    Sum absolute concentration (ng/ml) of all intakes via linear superposition.
    Heaviside: H(t - tau_i) ensures future intakes don't contribute.
    C_total(t) = SUM_i C_i(t - tau_i) * H(t - tau_i)
    """
    total = 0.0
    for intake in intakes:
        if intake.get("substance") != substance:
            continue
        intake_time = datetime.fromisoformat(intake["timestamp"])
        hours_since = (target_time - intake_time).total_seconds() / 3600.0
        if hours_since < 0:  # Heaviside: future intakes contribute 0
            continue
        dose = intake.get("dose_mg") or default_dose
        conc = conc_fn(hours_since, dose)
        if conc > 0.01:
            total += conc
    return total


def compute_substance_level(
    intakes: list[dict],
    target_time: datetime,
    substance: str,
    level_fn,
    default_dose: float,
) -> float:
    """
    Sum relative level (0-1+) of all intakes via superposition.
    """
    total = 0.0
    for intake in intakes:
        if intake.get("substance") != substance:
            continue
        intake_time = datetime.fromisoformat(intake["timestamp"])
        hours_since = (target_time - intake_time).total_seconds() / 3600.0
        if hours_since < 0:
            continue
        dose = intake.get("dose_mg") or default_dose
        effect = level_fn(hours_since, dose)
        if effect > 0.005:
            total += effect
    return total


# ── DDI Warning System ───────────────────────────────────────────────

def check_ddi_warnings(intakes: list[dict], target_time: datetime) -> list[dict]:
    """
    Check drug-drug interactions at the given time.
    Returns list of warning dicts: {severity, type, title, message}.

    Checks:
    1. CYP2D6 Phaenokonversion (Codein + D-Amphetamin)
    2. Serotonin-Syndrom-Risiko (Opioid + Triple-Stimulanz-Stack)
    3. Paracetamol-Hepatotoxizitaet (kumulative Dosis + Fasten)
    4. Extreme ZNS-Stimulanzien-Last
    """
    warnings = []

    # Current concentrations (ng/ml)
    elv_conc = compute_substance_load_ngml(
        intakes, target_time, "elvanse",
        elvanse_concentration, ELVANSE_DEFAULT_DOSE_MG,
    )
    med_ir_conc = compute_substance_load_ngml(
        intakes, target_time, "medikinet",
        medikinet_ir_concentration, MEDIKINET_DEFAULT_DOSE_MG,
    )
    med_ret_conc = compute_substance_load_ngml(
        intakes, target_time, "medikinet_retard",
        medikinet_retard_concentration, MEDIKINET_RETARD_DEFAULT_DOSE_MG,
    )
    caff_conc = compute_substance_load_ngml(
        intakes, target_time, "mate",
        caffeine_concentration, MATE_CAFFEINE_MG,
    )
    cod_conc = compute_substance_load_ngml(
        intakes, target_time, "co_dafalgan",
        codein_concentration, CO_DAFALGAN_DEFAULT_DOSE_MG,
    )

    # Thresholds (20% of user Cmax = clinically meaningful)
    d_amph_thresh = allometric_cmax(CMAX_REF["elvanse"], USER_WEIGHT_KG) * 0.2
    mph_thresh = allometric_cmax(CMAX_REF["medikinet_ir"], USER_WEIGHT_KG) * 0.2

    stimulant_active = (
        elv_conc > d_amph_thresh
        or med_ir_conc > mph_thresh
        or med_ret_conc > mph_thresh
    )

    # --- 1. CYP2D6-Blockade: analgetisches Versagen ---
    if cod_conc > 1.0 and stimulant_active:
        warnings.append({
            "severity": "critical",
            "type": "cyp2d6_blockade",
            "title": "CYP2D6-Blockade: Analgetisches Versagen",
            "message": (
                "D-Amphetamin blockiert CYP2D6 kompetitiv. "
                "Codein wird NICHT zu Morphin konvertiert -- "
                "kaum Schmerzlinderung. "
                "NICHT die Co-Dafalgan-Dosis erhoehen! "
                "Risiko: Paracetamol-Ueberdosis bei Glutathion-Depletion (Fasten)."
            ),
        })

    # --- 2. Serotonin-Syndrom-Risiko ---
    total_stim_norm = (
        elv_conc / max(d_amph_thresh * 5, 1)
        + (med_ir_conc + med_ret_conc) / max(mph_thresh * 5, 1)
        + caff_conc / 1500.0
    )
    if cod_conc > 1.0 and total_stim_norm > 0.3:
        warnings.append({
            "severity": "critical",
            "type": "serotonin_syndrome",
            "title": "Serotonin-Syndrom-Risiko",
            "message": (
                "Opioid (Codein) + Stimulanzien-Stack: "
                "serotonerge Exzitotoxizitaet moeglich. "
                "Symptome: Klonus, Hyperreflexie, Diaphorese, Tremor, Agitation. "
                "Bei Symptomen sofort aerztliche Hilfe!"
            ),
        })

    # --- 3. Paracetamol-Kumulation bei Fasten ---
    if USER_IS_FASTING:
        start_24h = target_time - timedelta(hours=24)
        para_total = 0.0
        for intake in intakes:
            if intake.get("substance") != "co_dafalgan":
                continue
            it = datetime.fromisoformat(intake["timestamp"])
            if start_24h <= it <= target_time:
                dose = intake.get("dose_mg") or CO_DAFALGAN_DEFAULT_DOSE_MG
                para_total += dose

        if para_total > PARACETAMOL_MAX_DAILY_FASTING_MG:
            warnings.append({
                "severity": "critical",
                "type": "paracetamol_toxicity",
                "title": "Paracetamol-Hepatotoxizitaet (Fasten!)",
                "message": (
                    f"Kumul. Paracetamol: {para_total:.0f}mg/24h. "
                    f"Max. bei Fasten: {PARACETAMOL_MAX_DAILY_FASTING_MG}mg. "
                    "Glutathion depletiert -- NAPQI-Neutralisierung stark eingeschraenkt."
                ),
            })
        elif para_total > 1000:
            warnings.append({
                "severity": "warning",
                "type": "paracetamol_caution",
                "title": "Paracetamol-Vorsicht (Fasten)",
                "message": (
                    f"Kumul. Paracetamol: {para_total:.0f}mg/24h. "
                    "Glutathion im Fastenzustand reduziert. Weitere Einnahme abwaegen."
                ),
            })

    # --- 4. ZNS-Ueberlastung ---
    cns_total = elv_conc + med_ir_conc + med_ret_conc
    cmax_stim_sum = (
        allometric_cmax(CMAX_REF["elvanse"], USER_WEIGHT_KG)
        + allometric_cmax(CMAX_REF["medikinet_ir"], USER_WEIGHT_KG)
    )
    if cns_total > cmax_stim_sum * 0.8 and caff_conc > 800:
        warnings.append({
            "severity": "warning",
            "type": "cns_overload",
            "title": "Extreme ZNS-Last",
            "message": (
                f"Stimulanzien: {cns_total:.1f} ng/ml + "
                f"Koffein: {caff_conc:.0f} ng/ml. "
                "Kardiovaskulaere Belastung sehr hoch. HRV und Ruhepuls beobachten."
            ),
        })

    return warnings


# ── HRV Penalty ──────────────────────────────────────────────────────

def hrv_penalty(
    hrv_ms: Optional[float],
    resting_hr: Optional[float],
    stim_level: float,
) -> float:
    """
    HRV-based penalty for Bio-Score.
    Low HRV + high stimulant level = sympathetic overdrive.
    Returns penalty: 0 to -15.
    """
    if hrv_ms is None:
        return 0.0

    penalty = 0.0

    # HRV below thresholds during stimulant peak = autonomic exhaustion
    if hrv_ms < 20 and stim_level > 0.5:
        penalty = -15.0
    elif hrv_ms < 30 and stim_level > 0.5:
        penalty = -10.0
    elif hrv_ms < 40 and stim_level > 0.3:
        penalty = -5.0
    elif hrv_ms < 50 and stim_level > 0.5:
        penalty = -3.0

    # Elevated resting HR during stimulant effect
    if resting_hr is not None:
        if resting_hr > 100:
            penalty -= 8.0
        elif resting_hr > 90 and stim_level > 0.3:
            penalty -= 5.0

    return max(-15.0, penalty)


def sleep_quality_modifier(sleep_duration_min: Optional[float],
                           sleep_confidence: Optional[float] = None) -> float:
    """Modifier based on last night's sleep. Returns -20 to +10."""
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


# ── Bio-Score composite ──────────────────────────────────────────────

def compute_bio_score(
    target_time: datetime,
    intakes: list[dict],
    sleep_duration_min: Optional[float] = None,
    sleep_confidence: Optional[float] = None,
    hrv_ms: Optional[float] = None,
    resting_hr: Optional[float] = None,
    water_intake_ml: Optional[int] = None,
    water_goal_ml: Optional[int] = None,
) -> dict:
    """
    Compute composite Bio-Score with allometric PK, DDI warnings,
    HRV autonomic monitoring, and hydration status.

    Returns dict with score, components, absolute ng/ml, warnings.
    """
    hour = target_time.hour + target_time.minute / 60.0

    # 1. Circadian base (0-60)
    circadian = circadian_base_score(hour)

    # 2. Elvanse boost (0-30): three-stage cascade
    elv_lv = compute_substance_level(
        intakes, target_time, "elvanse",
        elvanse_level, ELVANSE_DEFAULT_DOSE_MG,
    )
    elvanse_boost = min(30.0, elv_lv * 30.0)

    # 3. Medikinet boost: IR + retard (0-25)
    med_ir_lv = compute_substance_level(
        intakes, target_time, "medikinet",
        medikinet_ir_level, MEDIKINET_DEFAULT_DOSE_MG,
    )
    med_ret_lv = compute_substance_level(
        intakes, target_time, "medikinet_retard",
        medikinet_retard_level, MEDIKINET_RETARD_DEFAULT_DOSE_MG,
    )
    med_combined = med_ir_lv + med_ret_lv
    medikinet_boost = min(25.0, med_combined * 25.0)

    # 4. Caffeine boost (0-15)
    caff_lv = compute_substance_level(
        intakes, target_time, "mate",
        caffeine_level, MATE_CAFFEINE_MG,
    )
    caffeine_boost = min(15.0, caff_lv * 15.0)

    # 5. Sleep modifier (-20 to +10)
    sleep_mod = sleep_quality_modifier(sleep_duration_min, sleep_confidence)

    # 6. HRV penalty (0 to -15)
    stim_peak = max(elv_lv, med_combined)
    hrv_pen = hrv_penalty(hrv_ms, resting_hr, stim_peak)

    # 7. Hydration modifier (-10 to +5)
    hydration_mod = 0.0
    if water_intake_ml is not None and water_goal_ml is not None and water_goal_ml > 0:
        from app.core.water_engine import hydration_bio_score_modifier
        hydration_mod = hydration_bio_score_modifier(
            water_intake_ml, water_goal_ml, hour,
        )

    # Composite
    raw_score = (circadian + elvanse_boost + medikinet_boost + caffeine_boost
                 + sleep_mod + hrv_pen + hydration_mod)
    score = max(0.0, min(100.0, raw_score))

    # Absolute concentrations (ng/ml)
    elv_conc = compute_substance_load_ngml(
        intakes, target_time, "elvanse",
        elvanse_concentration, ELVANSE_DEFAULT_DOSE_MG,
    )
    med_ir_conc = compute_substance_load_ngml(
        intakes, target_time, "medikinet",
        medikinet_ir_concentration, MEDIKINET_DEFAULT_DOSE_MG,
    )
    med_ret_conc = compute_substance_load_ngml(
        intakes, target_time, "medikinet_retard",
        medikinet_retard_concentration, MEDIKINET_RETARD_DEFAULT_DOSE_MG,
    )
    caff_conc = compute_substance_load_ngml(
        intakes, target_time, "mate",
        caffeine_concentration, MATE_CAFFEINE_MG,
    )
    cod_conc = compute_substance_load_ngml(
        intakes, target_time, "co_dafalgan",
        codein_concentration, CO_DAFALGAN_DEFAULT_DOSE_MG,
    )

    # CNS load (relative sum)
    cns_load = elv_lv + med_combined + caff_lv

    # DDI warnings
    ddi_warnings = check_ddi_warnings(intakes, target_time)

    # Phase
    phase = _determine_phase(stim_peak, caff_lv, hour)

    return {
        "score": round(score, 1),
        "circadian": round(circadian, 1),
        "elvanse_boost": round(elvanse_boost, 1),
        "medikinet_boost": round(medikinet_boost, 1),
        "caffeine_boost": round(caffeine_boost, 1),
        "sleep_modifier": round(sleep_mod, 1),
        "hrv_penalty": round(hrv_pen, 1),
        # Relative levels (0-1+)
        "elvanse_level": round(elv_lv, 3),
        "medikinet_level": round(med_combined, 3),
        "caffeine_level": round(caff_lv, 3),
        "codein_level": round(
            cod_conc / max(allometric_cmax(CMAX_REF.get("codein", 100), USER_WEIGHT_KG), 1),
            3,
        ),
        # Absolute concentrations (ng/ml)
        "elvanse_ng_ml": round(elv_conc, 1),
        "medikinet_ng_ml": round(med_ir_conc + med_ret_conc, 1),
        "caffeine_ng_ml": round(caff_conc, 0),
        "codein_ng_ml": round(cod_conc, 1),
        # Composite
        "cns_load": round(cns_load, 3),
        "hydration_modifier": round(hydration_mod, 1),
        "phase": phase,
        "timestamp": target_time.isoformat(),
        "warnings": ddi_warnings,
    }


def _determine_phase(stim_level: float, caffeine_lv: float, hour: float) -> str:
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
    hrv_ms: Optional[float] = None,
    resting_hr: Optional[float] = None,
) -> list[dict]:
    """
    Generate Bio-Score data points for a full day at given interval.
    """
    points = []
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(0, 24 * 60, interval_minutes):
        t = start + timedelta(minutes=i)
        point = compute_bio_score(
            t, intakes, sleep_duration_min, sleep_confidence,
            hrv_ms, resting_hr,
        )
        points.append(point)

    return points
