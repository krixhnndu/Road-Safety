"""
db.py
SQLite persistence for the Crash and Hazard databases.

In the original Streamlit app, crashes/hazards lived in `st.session_state`
and were flushed to crash_database.csv / hazard_database.csv on every change.
Here they live in a small SQLite database (datasets/app.db) so entries
survive server restarts. The database is seeded once from the original
CSV snapshots on first run.
"""
import os
import sqlite3
import csv
from datetime import datetime

DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
DB_PATH = os.path.join(DATASETS_DIR, "app.db")

CRASH_COLS = ['crash_id', 'segment_id', 'severity', 'date', 'time', 'description']
HAZARD_COLS = ['hazard_id', 'segment_id', 'hazard_type', 'start_time', 'end_time',
               'date', 'temp_speed', 'description']


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_empty(conn, table):
    cur = conn.execute(f"SELECT COUNT(*) AS n FROM {table}")
    return cur.fetchone()["n"] == 0


def init_db():
    """Create tables if they don't exist, and seed from the original CSV
    snapshots the very first time the app runs."""
    first_run = not os.path.exists(DB_PATH)
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crashes (
            crash_id INTEGER PRIMARY KEY,
            segment_id INTEGER NOT NULL,
            severity TEXT,
            date TEXT,
            time TEXT,
            description TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hazards (
            hazard_id INTEGER PRIMARY KEY,
            segment_id INTEGER NOT NULL,
            hazard_type TEXT,
            start_time TEXT,
            end_time TEXT,
            date TEXT,
            temp_speed REAL,
            description TEXT
        )
    """)
    conn.commit()

    if first_run or _table_empty(conn, "crashes"):
        _seed_from_csv(conn, "crashes", os.path.join(DATASETS_DIR, "crash_database_seed.csv"), CRASH_COLS)
    if first_run or _table_empty(conn, "hazards"):
        _seed_from_csv(conn, "hazards", os.path.join(DATASETS_DIR, "hazard_database_seed.csv"), HAZARD_COLS)

    conn.close()


def _seed_from_csv(conn, table, path, cols):
    if not os.path.exists(path):
        return
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return
    placeholders = ",".join(["?"] * len(cols))
    for row in rows:
        values = [row.get(c) or None for c in cols]
        try:
            conn.execute(f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})", values)
        except Exception:
            continue
    conn.commit()


# ─── Crashes ────────────────────────────────────────────────────────────────
def get_all_crashes():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM crashes ORDER BY crash_id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_crash(segment_id, severity, date, time, description):
    conn = get_conn()
    cur = conn.execute("SELECT MAX(crash_id) AS m FROM crashes")
    next_id = (cur.fetchone()["m"] or 0) + 1
    conn.execute(
        "INSERT INTO crashes (crash_id, segment_id, severity, date, time, description) VALUES (?,?,?,?,?,?)",
        (next_id, segment_id, severity, date, time, description),
    )
    conn.commit()
    conn.close()
    return next_id


def delete_crash(crash_id):
    conn = get_conn()
    conn.execute("DELETE FROM crashes WHERE crash_id = ?", (crash_id,))
    conn.commit()
    conn.close()


# ─── Hazards ────────────────────────────────────────────────────────────────
def get_all_hazards():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM hazards ORDER BY hazard_id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_hazard(segment_id, hazard_type, start_time, end_time, date, temp_speed, description):
    conn = get_conn()
    cur = conn.execute("SELECT MAX(hazard_id) AS m FROM hazards")
    next_id = (cur.fetchone()["m"] or 0) + 1
    conn.execute(
        "INSERT INTO hazards (hazard_id, segment_id, hazard_type, start_time, end_time, date, temp_speed, description) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (next_id, segment_id, hazard_type, start_time, end_time, date, temp_speed, description),
    )
    conn.commit()
    conn.close()
    return next_id


def delete_hazard(hazard_id):
    conn = get_conn()
    conn.execute("DELETE FROM hazards WHERE hazard_id = ?", (hazard_id,))
    conn.commit()
    conn.close()


def purge_expired_hazards():
    """Remove hazards whose date is in the past, or whose end_time has
    passed on today's date — ported from apply_hazard_expiry()."""
    today = datetime.now().date()
    now_time = datetime.now().time()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM hazards").fetchall()
    to_delete = []
    for r in rows:
        try:
            hz_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if hz_date < today:
            to_delete.append(r["hazard_id"])
        elif hz_date == today:
            try:
                end_t = datetime.strptime(str(r["end_time"]), "%H:%M").time()
                if end_t < now_time:
                    to_delete.append(r["hazard_id"])
            except Exception:
                continue
    for hid in to_delete:
        conn.execute("DELETE FROM hazards WHERE hazard_id = ?", (hid,))
    conn.commit()
    conn.close()
