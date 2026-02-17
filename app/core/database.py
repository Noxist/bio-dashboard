"""
SQLite database setup and access layer.
Schema: intake_events, subjective_logs, health_snapshots.
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
    substance   TEXT    NOT NULL CHECK(substance IN ('elvanse','mate','medikinet','medikinet_retard','other')),
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
                          inner_unrest: Optional[int] = None) -> int:
    ts = timestamp or datetime.now().isoformat()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO subjective_logs
               (timestamp, focus, mood, energy, tags, appetite, inner_unrest)
               VALUES (?,?,?,?,?,?,?)""",
            (ts, focus, mood, energy, tags, appetite, inner_unrest),
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
