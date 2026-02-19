"""
Bio-Dashboard Configuration.
All settings via environment variables with sensible defaults.
"""

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(os.getenv("BIO_DATA_DIR", "/data"))
DB_PATH = BASE_DIR / "bio.db"

# --- Home Assistant ---
HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")
HA_POLL_INTERVAL_SEC = int(os.getenv("HA_POLL_INTERVAL_SEC", "900"))  # 15 min

# --- Auth ---
API_KEY = os.getenv("BIO_API_KEY", "")

# --- User Anthropometrics ---
USER_WEIGHT_KG: float = float(os.getenv("USER_WEIGHT_KG", "96"))
USER_HEIGHT_CM: float = float(os.getenv("USER_HEIGHT_CM", "192"))
USER_AGE: int = int(os.getenv("USER_AGE", "19"))
USER_IS_SMOKER: bool = os.getenv("USER_IS_SMOKER", "false").lower() == "true"
USER_IS_FASTING: bool = os.getenv("USER_IS_FASTING", "true").lower() == "true"

# --- Timezone ---
TIMEZONE = os.getenv("TZ", "Europe/Zurich")

# --- Printer ---
PRINTER_URL = os.getenv("PRINTER_URL", "http://printer-api:8080")
PRINTER_API_KEY = os.getenv("PRINTER_API_KEY", "")

# --- OpenAI (for future Daily Briefing) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Water / Hydration ---
# Evidence-based hydration model (Gemini research, EFSA 2010, IOM 2004, Holliday-Segar)
WATER_BASE_ML_PER_KG: float = float(os.getenv("WATER_BASE_ML_PER_KG", "33.3"))  # midpoint 30-35 ml/kg
WATER_DRUG_MODIFIER_ML: int = int(os.getenv("WATER_DRUG_MODIFIER_ML", "110"))     # +110ml for Elvanse 5% REE
WATER_ACTIVITY_ML_PER_1K_STEPS: int = int(os.getenv("WATER_ACTIVITY_ML_PER_1K", "60"))  # +60ml per 1k steps >4k
WATER_ACTIVITY_BASELINE_STEPS: int = int(os.getenv("WATER_ACTIVITY_BASELINE", "4000"))   # sedentary baseline
WATER_FASTING_MODIFIER_ML: int = int(os.getenv("WATER_FASTING_MODIFIER_ML", "500"))      # OMAD food moisture loss
WATER_MAX_HOURLY_ML: int = int(os.getenv("WATER_MAX_HOURLY_ML", "800"))           # renal excretion safety cap
WATER_WAKING_HOURS: int = int(os.getenv("WATER_WAKING_HOURS", "16"))              # assumed waking hours
WATER_DEFAULT_GOAL_ML: int = int(os.getenv("WATER_DEFAULT_GOAL_ML", "3200"))      # fallback before calc
# Dehydration detection (wearable telemetry)
DEHYDRATION_HR_DRIFT_BPM: float = float(os.getenv("DEHYDRATION_HR_DRIFT", "4.0"))   # HR rise threshold
DEHYDRATION_HRV_DROP_PCT: float = float(os.getenv("DEHYDRATION_HRV_DROP", "15.0"))  # % HRV drop threshold
# Migraine prophylaxis electrolyte targets (mg/day)
MIGRAINE_MG_TARGET: int = int(os.getenv("MIGRAINE_MG_TARGET", "500"))    # Magnesium
MIGRAINE_K_TARGET: int = int(os.getenv("MIGRAINE_K_TARGET", "1500"))     # Potassium
# Watch server auth (reuse BIO_API_KEY)
WATER_WATCH_TOKEN: str = os.getenv("WATER_WATCH_TOKEN", "") or API_KEY

# --- Allometric Reference ---
REFERENCE_WEIGHT_KG: float = 70.0  # Standard reference adult weight

# --- Elvanse (Lisdexamfetamine -> d-Amphetamine) ---
# Three-stage cascade model: GI absorption (PEPT1) -> erythrocyte hydrolysis -> elimination
# Hutson et al. 2017, Ermer et al. 2016
ELVANSE_DEFAULT_DOSE_MG = int(os.getenv("ELVANSE_DEFAULT_DOSE_MG", "40"))
ELVANSE_KA_ABS = float(os.getenv("ELVANSE_KA_ABS", "2.0"))   # h^-1, PEPT1 GI absorption rate
ELVANSE_KA = float(os.getenv("ELVANSE_KA", "0.78"))           # h^-1, erythrocyte hydrolysis rate
ELVANSE_KE = float(os.getenv("ELVANSE_KE", "0.088"))          # h^-1, d-amph elimination (t1/2 ~10-12h)
ELVANSE_F = float(os.getenv("ELVANSE_F", "0.964"))            # Bioavailability 96.4%

# --- Medikinet IR (Methylphenidate immediate release) ---
# Bateman PK params from Kim et al. 2017, Markowitz et al. 2000
MEDIKINET_DEFAULT_DOSE_MG = int(os.getenv("MEDIKINET_DEFAULT_DOSE_MG", "10"))
MEDIKINET_IR_KA = float(os.getenv("MEDIKINET_IR_KA", "1.72"))   # h^-1, fast absorption (fasted MMC)
MEDIKINET_IR_KE = float(os.getenv("MEDIKINET_IR_KE", "0.28"))   # h^-1, CES1 hepatic clearance, t1/2 ~2.5h
MEDIKINET_F = float(os.getenv("MEDIKINET_F", "0.30"))           # Bioavailability ~30% (first-pass)

# --- Medikinet retard (Methylphenidate modified release, FASTED state) ---
# Fasted: single-peak collapse, enteric coating dissolves prematurely
# Haessler et al. 2008, Kim et al. 2017
MEDIKINET_RETARD_DEFAULT_DOSE_MG = int(os.getenv("MEDIKINET_RETARD_DEFAULT_DOSE_MG", "30"))
MEDIKINET_RETARD_KA = float(os.getenv("MEDIKINET_RETARD_KA", "1.2"))   # h^-1, collapsed uniform absorption
MEDIKINET_RETARD_KE = float(os.getenv("MEDIKINET_RETARD_KE", "0.28"))  # h^-1, same elimination

# --- Caffeine (Lamate / Mate) ---
# Kamimori et al. 2002, Seng et al. 2009
# Lamate: 23mg/100ml x 330ml = 75.9mg ~ 76mg per can
MATE_CAFFEINE_MG = int(os.getenv("MATE_CAFFEINE_MG", "76"))
CAFFEINE_KA = float(os.getenv("CAFFEINE_KA", "2.5"))    # h^-1, near-instant GI absorption (fasted)
CAFFEINE_KE = float(os.getenv("CAFFEINE_KE", "0.16"))   # h^-1, non-smoker CYP1A2 t1/2 ~4.3h

# --- Co-Dafalgan (Paracetamol 500mg + Codein 30mg per tablet) ---
CO_DAFALGAN_DEFAULT_DOSE_MG = int(os.getenv("CO_DAFALGAN_DEFAULT_DOSE_MG", "500"))  # mg paracetamol
CODEIN_RATIO = 30.0 / 500.0  # 30mg codein per 500mg paracetamol
CO_DAFALGAN_CODEIN_KA = float(os.getenv("CO_DAFALGAN_CODEIN_KA", "1.7"))         # h^-1
CO_DAFALGAN_CODEIN_KE = float(os.getenv("CO_DAFALGAN_CODEIN_KE", "0.23"))        # h^-1, t1/2 ~3h
CO_DAFALGAN_PARACETAMOL_KA = float(os.getenv("CO_DAFALGAN_PARACETAMOL_KA", "3.0"))  # h^-1
CO_DAFALGAN_PARACETAMOL_KE = float(os.getenv("CO_DAFALGAN_PARACETAMOL_KE", "0.28")) # h^-1, t1/2 ~2.5h
PARACETAMOL_MAX_DAILY_FASTING_MG = 2000  # Reduced from 4000mg due to glutathione depletion

# --- Population Cmax Reference Values (ng/ml at standard dose, 70kg) ---
# These are allometrically scaled: Cmax_user = Cmax_ref * (70 / weight_user)
CMAX_REF = {
    "elvanse": 36.0,            # d-Amph from 40mg LDX (Ermer et al. 2016)
    "medikinet_ir": 6.0,        # MPH from 10mg IR (Kim et al. 2017, F~30%)
    "medikinet_retard": 12.0,   # MPH from 30mg MR fasted (Haessler et al. 2008)
    "caffeine": 1500.0,         # 76mg caffeine (Vd ~0.7 L/kg, F ~99%)
    "codein": 100.0,            # 30mg codein (F ~90%)
    "paracetamol": 10000.0,     # 500mg paracetamol (F ~90%)
}

# --- HA Sensor entity IDs ---
# Note: all health sensors use the "_2" suffix (HealthSync via second device entry)
HA_SENSORS = {
    "heart_rate": "sensor.pixel_9_pro_xl_heart_rate_2",
    "resting_hr": "sensor.pixel_9_pro_xl_resting_heart_rate_2",
    "hrv": "sensor.pixel_9_pro_xl_heart_rate_variability_2",
    "sleep_duration": "sensor.pixel_9_pro_xl_sleep_duration_2",
    "spo2": "sensor.pixel_9_pro_xl_oxygen_saturation_2",
    "respiratory_rate": "sensor.pixel_9_pro_xl_respiratory_rate_2",
    "steps": "sensor.pixel_9_pro_xl_daily_steps_2",
    "calories": "sensor.pixel_9_pro_xl_active_calories_burned_2",
    "sleepmode": "input_boolean.sleepmode",
    "inbed": "input_boolean.inbed",
    # Water tracking + weight (from Google Fit via HealthSync)
    "water_daily": "sensor.water_tracker_daily",
    "user_weight": "sensor.pixel_9_pro_xl_weight_2",
    "user_weight_fallback": "input_number.user_weight_kg",
}
