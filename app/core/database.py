"""
SQLite database setup and access layer.
Schema: intake_events, subjective_logs, health_snapshots, water_events, weight_log.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from app.config import DB_PATH

_local = threading.local()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS intake_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    substance   TEXT    NOT NULL CHECK(substance IN ('elvanse','mate','medikinet','medikinet_retard','co_dafalgan','other')),
    dose_mg     REAL,
    notes       TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS subjective_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    focus       INTEGER CHECK(focus BETWEEN 1 AND 10),
    mood        INTEGER CHECK(mood BETWEEN 1 AND 10),
    energy      INTEGER CHECK(energy BETWEEN 1 AND 10),
    appetite    INTEGER CHECK(appetite BETWEEN 1 AND 10),
    inner_unrest INTEGER CHECK(inner_unrest BETWEEN 1 AND 10),
    pain_severity INTEGER CHECK(pain_severity BETWEEN 0 AND 10),
    aura_duration_min INTEGER,
    aura_type   TEXT,
    photophobia INTEGER CHECK(photophobia IN (0, 1)),
    phonophobia INTEGER CHECK(phonophobia IN (0, 1)),
    tags        TEXT    DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS health_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    heart_rate      REAL,
    resting_hr      REAL,
    hrv             REAL,
    sleep_duration  REAL,
    sleep_confidence REAL,
    spo2            REAL,
    respiratory_rate REAL,
    steps           INTEGER,
    calories        REAL,
    source          TEXT    DEFAULT 'ha' CHECK(source IN ('ha','manual','watch'))
);

CREATE INDEX IF NOT EXISTS idx_intake_ts ON intake_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_subjective_ts ON subjective_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_health_ts ON health_snapshots(timestamp);

CREATE TABLE IF NOT EXISTS meal_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    meal_type   TEXT    NOT NULL CHECK(meal_type IN ('fruehstueck','mittagessen','abendessen','snack')),
    notes       TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_meal_ts ON meal_events(timestamp);

CREATE TABLE IF NOT EXISTS water_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    amount_ml   INTEGER NOT NULL,
    source      TEXT    DEFAULT 'watch' CHECK(source IN ('watch','manual','ha')),
    notes       TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_water_ts ON water_events(timestamp);

CREATE TABLE IF NOT EXISTS water_goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL UNIQUE,
    goal_ml     INTEGER NOT NULL,
    base_ml     INTEGER,
    drug_mod_ml INTEGER DEFAULT 0,
    fasting_mod_ml INTEGER DEFAULT 0,
    activity_mod_ml INTEGER DEFAULT 0,
    weight_kg   REAL,
    steps       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_water_goal_date ON water_goals(date);

CREATE TABLE IF NOT EXISTS weight_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    weight_kg   REAL    NOT NULL,
    source      TEXT    DEFAULT 'manual' CHECK(source IN ('manual','ha','watch','google_fit'))
);

CREATE INDEX IF NOT EXISTS idx_weight_ts ON weight_log(timestamp);
"""


def get_connection() -> sqlite3.Connection:
    """Thread-local SQLite connection with WAL mode."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def db_cursor():
    """Yield a cursor, auto-commit on success, rollback on error."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_tables():
    """
    Run all necessary schema migrations.
    SQLite can't ALTER CHECK constraints, so we recreate tables when needed.
    """
    conn = get_connection()
    cur = conn.cursor()

    # --- Migration 1: intake_events CHECK constraint ---
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_events'")
    row = cur.fetchone()
    if row:
        create_sql = row[0] or ""
        # Need migration if missing medikinet_retard
        if "medikinet_retard" not in create_sql:
            print("[bio-db] Migrating intake_events: adding medikinet_retard", flush=True)
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS intake_events_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    substance   TEXT    NOT NULL CHECK(substance IN ('elvanse','mate','medikinet','medikinet_retard','other')),
                    dose_mg     REAL,
                    notes       TEXT    DEFAULT ''
                );
                INSERT INTO intake_events_new (id, timestamp, substance, dose_mg, notes)
                    SELECT id, timestamp,
                           CASE WHEN substance='lamotrigin' THEN 'other' ELSE substance END,
                           dose_mg, notes
                    FROM intake_events;
                DROP TABLE intake_events;
                ALTER TABLE intake_events_new RENAME TO intake_events;
                CREATE INDEX IF NOT EXISTS idx_intake_ts ON intake_events(timestamp);
            """)
            conn.commit()
            print("[bio-db] intake_events migration complete", flush=True)

    # --- Migration 2: subjective_logs add appetite + inner_unrest ---
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='subjective_logs'")
    row = cur.fetchone()
    if row:
        create_sql = row[0] or ""
        if "appetite" not in create_sql:
            print("[bio-db] Migrating subjective_logs: adding appetite, inner_unrest", flush=True)
            try:
                cur.execute("ALTER TABLE subjective_logs ADD COLUMN appetite INTEGER CHECK(appetite BETWEEN 1 AND 10)")
                cur.execute("ALTER TABLE subjective_logs ADD COLUMN inner_unrest INTEGER CHECK(inner_unrest BETWEEN 1 AND 10)")
                conn.commit()
                print("[bio-db] subjective_logs migration complete", flush=True)
            except Exception as e:
                print(f"[bio-db] subjective_logs migration note: {e}", flush=True)

    # --- Migration 3: subjective_logs add migraine fields ---
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='subjective_logs'")
    row = cur.fetchone()
    if row:
        create_sql = row[0] or ""
        if "pain_severity" not in create_sql:
            print("[bio-db] Migrating subjective_logs: adding migraine fields", flush=True)
            for col_sql in [
                "ALTER TABLE subjective_logs ADD COLUMN pain_severity INTEGER CHECK(pain_severity BETWEEN 0 AND 10)",
                "ALTER TABLE subjective_logs ADD COLUMN aura_duration_min INTEGER",
                "ALTER TABLE subjective_logs ADD COLUMN aura_type TEXT",
                "ALTER TABLE subjective_logs ADD COLUMN photophobia INTEGER CHECK(photophobia IN (0, 1))",
                "ALTER TABLE subjective_logs ADD COLUMN phonophobia INTEGER CHECK(phonophobia IN (0, 1))",
            ]:
                try:
                    cur.execute(col_sql)
                except Exception as e:
                    print(f"[bio-db] migraine migration note: {e}", flush=True)
            conn.commit()
            print("[bio-db] migraine fields migration complete", flush=True)

    # --- Migration 4: intake_events add co_dafalgan to CHECK ---
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_events'")
    row = cur.fetchone()
    if row:
        create_sql = row[0] or ""
        if "co_dafalgan" not in create_sql:
            print("[bio-db] Migrating intake_events: adding co_dafalgan", flush=True)
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS intake_events_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    substance   TEXT    NOT NULL CHECK(substance IN ('elvanse','mate','medikinet','medikinet_retard','co_dafalgan','other')),
                    dose_mg     REAL,
                    notes       TEXT    DEFAULT ''
                );
                INSERT INTO intake_events_new (id, timestamp, substance, dose_mg, notes)
                    SELECT id, timestamp, substance, dose_mg, notes
                    FROM intake_events;
                DROP TABLE intake_events;
                ALTER TABLE intake_events_new RENAME TO intake_events;
                CREATE INDEX IF NOT EXISTS idx_intake_ts ON intake_events(timestamp);
            """)
            conn.commit()
            print("[bio-db] intake_events co_dafalgan migration complete", flush=True)

    # --- Migration 5: weight_log add google_fit to source CHECK ---
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='weight_log'")
    row = cur.fetchone()
    if row:
        create_sql = row[0] or ""
        if "google_fit" not in create_sql:
            print("[bio-db] Migrating weight_log: adding google_fit source", flush=True)
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS weight_log_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    weight_kg   REAL    NOT NULL,
                    source      TEXT    DEFAULT 'manual' CHECK(source IN ('manual','ha','watch','google_fit'))
                );
                INSERT INTO weight_log_new (id, timestamp, weight_kg, source)
                    SELECT id, timestamp, weight_kg, source
                    FROM weight_log;
                DROP TABLE weight_log;
                ALTER TABLE weight_log_new RENAME TO weight_log;
                CREATE INDEX IF NOT EXISTS idx_weight_ts ON weight_log(timestamp);
            """)
            conn.commit()
            print("[bio-db] weight_log migration complete", flush=True)

    # --- Migration 6: fix weight values stored in grams ---
    # Convert any weight_kg > 500 (clearly grams, not kg) to proper kg
    cur.execute("SELECT COUNT(*) FROM weight_log WHERE weight_kg > 500")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"[bio-db] Fixing {count} weight entries stored in grams", flush=True)
        cur.execute("UPDATE weight_log SET weight_kg = weight_kg / 1000.0 WHERE weight_kg > 500")
        conn.commit()
        print("[bio-db] Weight gram→kg fix complete", flush=True)


def init_db():
    """Create tables if they don't exist, run migrations."""
    _migrate_tables()
    with db_cursor() as cur:
        cur.executescript(SCHEMA_SQL)
    print("[bio-db] Database initialized at", DB_PATH, flush=True)


# --- CRUD helpers ---

def insert_intake(substance: str, dose_mg: Optional[float] = None,
                  notes: str = "", timestamp: Optional[str] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO intake_events (timestamp, substance, dose_mg, notes) VALUES (?,?,?,?)",
            (ts, substance, dose_mg, notes),
        )
        return cur.lastrowid


def insert_subjective_log(focus: int, mood: int, energy: int,
                          tags: str = "[]", timestamp: Optional[str] = None,
                          appetite: Optional[int] = None,
                          inner_unrest: Optional[int] = None,
                          pain_severity: Optional[int] = None,
                          aura_duration_min: Optional[int] = None,
                          aura_type: Optional[str] = None,
                          photophobia: Optional[int] = None,
                          phonophobia: Optional[int] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO subjective_logs
               (timestamp, focus, mood, energy, tags, appetite, inner_unrest,
                pain_severity, aura_duration_min, aura_type, photophobia, phonophobia)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ts, focus, mood, energy, tags, appetite, inner_unrest,
             pain_severity, aura_duration_min, aura_type, photophobia, phonophobia),
        )
        return cur.lastrowid


def insert_health_snapshot(data: dict, source: str = "ha",
                           timestamp: Optional[str] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO health_snapshots
               (timestamp, heart_rate, resting_hr, hrv, sleep_duration,
                sleep_confidence, spo2, respiratory_rate, steps, calories, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts,
                data.get("heart_rate"),
                data.get("resting_hr"),
                data.get("hrv"),
                data.get("sleep_duration"),
                data.get("sleep_confidence"),
                data.get("spo2"),
                data.get("respiratory_rate"),
                data.get("steps"),
                data.get("calories"),
                source,
            ),
        )
        return cur.lastrowid


def query_intakes(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM intake_events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]


def query_subjective_logs(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM subjective_logs WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]


def query_health_snapshots(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM health_snapshots WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]


def get_latest_intake(substance: str) -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM intake_events WHERE substance=? ORDER BY timestamp DESC LIMIT 1",
            (substance,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_latest_health_snapshot() -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM health_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_todays_intakes() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return query_intakes(f"{today}T00:00:00", f"{today}T23:59:59")


def get_todays_logs() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return query_subjective_logs(f"{today}T00:00:00", f"{today}T23:59:59")


def delete_intake(intake_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM intake_events WHERE id=?", (intake_id,))
        return cur.rowcount > 0


def delete_subjective_log(log_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM subjective_logs WHERE id=?", (log_id,))
        return cur.rowcount > 0


def insert_meal(meal_type: str, notes: str = "", timestamp: Optional[str] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO meal_events (timestamp, meal_type, notes) VALUES (?,?,?)",
            (ts, meal_type, notes),
        )
        return cur.lastrowid


def get_todays_meals() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM meal_events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (f"{today}T00:00:00", f"{today}T23:59:59"),
        )
        return [dict(r) for r in cur.fetchall()]


def query_meals(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM meal_events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_meal(meal_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM meal_events WHERE id=?", (meal_id,))
        return cur.rowcount > 0


# --- Water tracking ---

def insert_water_event(amount_ml: int, source: str = "watch",
                       notes: str = "", timestamp: Optional[str] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO water_events (timestamp, amount_ml, source, notes) VALUES (?,?,?,?)",
            (ts, amount_ml, source, notes),
        )
        return cur.lastrowid


def query_water_events(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM water_events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]


def get_todays_water_events() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return query_water_events(f"{today}T00:00:00", f"{today}T23:59:59")


def get_todays_water_total() -> int:
    """Sum of all water intake today in ml."""
    events = get_todays_water_events()
    return sum(e.get("amount_ml", 0) for e in events)


def get_last_water_event() -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM water_events ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None


def delete_water_event(event_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM water_events WHERE id=?", (event_id,))
        return cur.rowcount > 0


def reset_todays_water() -> int:
    """Delete all water events for today. Returns count of deleted rows."""
    today = datetime.now().strftime("%Y-%m-%d")
    with db_cursor() as cur:
        cur.execute(
            "DELETE FROM water_events WHERE timestamp LIKE ?",
            (f"{today}%",),
        )
        return cur.rowcount


# --- Water goals ---

def upsert_water_goal(date: str, goal_ml: int, base_ml: int = 0,
                      drug_mod_ml: int = 0, fasting_mod_ml: int = 0,
                      activity_mod_ml: int = 0, weight_kg: float = 0,
                      steps: int = 0) -> int:
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO water_goals (date, goal_ml, base_ml, drug_mod_ml,
                   fasting_mod_ml, activity_mod_ml, weight_kg, steps)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                   goal_ml=excluded.goal_ml, base_ml=excluded.base_ml,
                   drug_mod_ml=excluded.drug_mod_ml, fasting_mod_ml=excluded.fasting_mod_ml,
                   activity_mod_ml=excluded.activity_mod_ml, weight_kg=excluded.weight_kg,
                   steps=excluded.steps""",
            (date, goal_ml, base_ml, drug_mod_ml, fasting_mod_ml,
             activity_mod_ml, weight_kg, steps),
        )
        return cur.lastrowid


def get_water_goal(date: str) -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM water_goals WHERE date=?", (date,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_water_goals_range(start_date: str, end_date: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM water_goals WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date),
        )
        return [dict(r) for r in cur.fetchall()]


# --- Weight tracking ---

def insert_weight(weight_kg: float, source: str = "manual",
                  timestamp: Optional[str] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO weight_log (timestamp, weight_kg, source) VALUES (?,?,?)",
            (ts, weight_kg, source),
        )
        return cur.lastrowid


def get_latest_weight() -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM weight_log ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None


def query_weight_log(start: str, end: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM weight_log WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start, end),
        )
        return [dict(r) for r in cur.fetchall()]
