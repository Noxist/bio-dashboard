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

# --- Elvanse (Lisdexamfetamine -> d-Amphetamine) ---
# Bateman PK params from Hutson et al. 2017, Ermer et al. 2016
ELVANSE_DEFAULT_DOSE_MG = int(os.getenv("ELVANSE_DEFAULT_DOSE_MG", "40"))
ELVANSE_KA = float(os.getenv("ELVANSE_KA", "0.78"))    # h^-1, d-amph appearance rate (prodrug hydrolysis)
ELVANSE_KE = float(os.getenv("ELVANSE_KE", "0.088"))   # h^-1, d-amph elimination (t1/2 ~10-12h)

# --- Medikinet IR (Methylphenidate immediate release) ---
# Bateman PK params from Kim et al. 2017, Markowitz et al. 2000
MEDIKINET_DEFAULT_DOSE_MG = int(os.getenv("MEDIKINET_DEFAULT_DOSE_MG", "10"))
MEDIKINET_IR_KA = float(os.getenv("MEDIKINET_IR_KA", "1.72"))   # h^-1, fast absorption
MEDIKINET_IR_KE = float(os.getenv("MEDIKINET_IR_KE", "0.28"))   # h^-1, t1/2 ~2.5h

# --- Medikinet retard (Methylphenidate modified release, FASTED state) ---
# In fasted state: single-peak Bateman, enteric coating dissolves prematurely
# Haessler et al. 2008, Kim et al. 2017
MEDIKINET_RETARD_DEFAULT_DOSE_MG = int(os.getenv("MEDIKINET_RETARD_DEFAULT_DOSE_MG", "30"))
MEDIKINET_RETARD_KA = float(os.getenv("MEDIKINET_RETARD_KA", "1.2"))   # h^-1, widened vs IR
MEDIKINET_RETARD_KE = float(os.getenv("MEDIKINET_RETARD_KE", "0.28"))  # h^-1, same elimination

# --- Caffeine (Lamate / Mate) ---
# Bateman PK params from Kamimori et al. 2002, Seng et al. 2009
# Lamate: 23mg/100ml x 330ml = 75.9mg ~ 76mg per can
MATE_CAFFEINE_MG = int(os.getenv("MATE_CAFFEINE_MG", "76"))
CAFFEINE_KA = float(os.getenv("CAFFEINE_KA", "2.5"))    # h^-1, mid-range (1.48-4.94)
CAFFEINE_KE = float(os.getenv("CAFFEINE_KE", "0.16"))   # h^-1, non-smoker t1/2 ~4.3h

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
}
