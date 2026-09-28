"""Два разбора в одном журнале: демо и камеры. Отметки мастера не смешиваются."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.rules import norm_grams

LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_mode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    mode TEXT PRIMARY KEY,
    section TEXT,
    planted INTEGER,
    age_days INTEGER,
    visible INTEGER,
    clock TEXT,
    weight_median REAL,
    weight_norm REAL,
    weight_hidden INTEGER,
    activity_text TEXT,
    activity_detail TEXT,
    phone INTEGER,
    thermal_fault INTEGER,
    control_grams REAL,
    frame_count INTEGER,
    still_fraction REAL,
    heat_note TEXT,
    detector_note TEXT,
    accelerated INTEGER,
    playback TEXT,
    zones TEXT,
    fault_zones TEXT
);
CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY,
    mode TEXT,
    zone TEXT,
    cell TEXT,
    t_min REAL,
    t_label TEXT,
    delta_c REAL,
    reason TEXT,
    cx_cm REAL,
    cy_cm REAL,
    track_id INTEGER,
    status TEXT,
    marked_by TEXT,
    marked_at TEXT,
    opened_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_hour (
    mode TEXT,
    day TEXT,
    hour INTEGER,
    fraction REAL,
    PRIMARY KEY (mode, day, hour)
);
CREATE TABLE IF NOT EXISTS hall (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    with LOCK:
        existing = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points'").fetchone()
        if existing is not None:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(points)")]
            if "mode" not in columns:
                conn.execute("DROP TABLE points")
                conn.execute("DROP TABLE IF EXISTS flock")
        conn.executescript(SCHEMA)
        run_columns = [row[1] for row in conn.execute("PRAGMA table_info(runs)")]
        if run_columns and "zones" not in run_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN zones TEXT")
        if run_columns and "fault_zones" not in run_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN fault_zones TEXT")
        point_columns = [row[1] for row in conn.execute("PRAGMA table_info(points)")]
        if point_columns and "opened_at" not in point_columns:
            conn.execute("ALTER TABLE points ADD COLUMN opened_at TEXT")
        row = conn.execute("SELECT active_mode FROM meta WHERE id = 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO meta (id, active_mode) VALUES (1, 'demo')")
            conn.commit()
    return conn


def save_hall(path: Path, plan: dict) -> None:
    conn = connect(path)
    payload = json.dumps(plan, ensure_ascii=False)
    with LOCK:
        conn.execute(
            "INSERT INTO hall (id, payload) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
            (payload,),
        )
        conn.commit()
    conn.close()


def load_hall(path: Path) -> dict | None:
    if not path.exists():
        return None
    conn = connect(path)
    row = conn.execute("SELECT payload FROM hall WHERE id = 1").fetchone()
    conn.close()
    if row is None:
        return None
    try:
        plan = json.loads(row["payload"])
    except json.JSONDecodeError:
        return None
    if not isinstance(plan, dict) or "length_m" not in plan:
        return None
    return plan


def active_mode(path: Path) -> str:
    conn = connect(path)
    mode = conn.execute("SELECT active_mode FROM meta WHERE id = 1").fetchone()["active_mode"]
    conn.close()
    return mode


def set_mode(path: Path, mode: str) -> dict:
    if mode not in {"demo", "live"}:
        raise ValueError("mode")
    conn = connect(path)
    with LOCK:
        conn.execute("UPDATE meta SET active_mode = ? WHERE id = 1", (mode,))
        conn.commit()
    conn.close()
    return state(path, mode)


def save_run(path: Path, result: dict, mode: str, keep_marks: bool = False) -> None:
    conn = connect(path)
    with LOCK:
        previous = {
            (row["zone"], row["cell"]): row
            for row in conn.execute("SELECT * FROM points WHERE mode = ?", (mode,))
        }
        conn.execute("DELETE FROM runs WHERE mode = ?", (mode,))
        conn.execute("DELETE FROM points WHERE mode = ?", (mode,))
        conn.execute(
            """
            INSERT INTO runs (
                mode, section, planted, age_days, visible, clock, weight_median, weight_norm,
                weight_hidden, activity_text, activity_detail, phone, thermal_fault,
                control_grams, frame_count, still_fraction, heat_note, detector_note,
                accelerated, playback, zones, fault_zones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mode,
                result.get("section") or ("демо-секция" if mode == "demo" else "секция"),
                result["planted"],
                result["age_days"],
                result["visible"],
                result["clock"],
                result["weight_median"],
                result["weight_norm"],
                1 if result["weight_hidden"] else 0,
                result["activity_text"],
                result["activity_detail"],
                1 if result["phone"] else 0,
                1 if result["thermal_fault"] else 0,
                result.get("control_grams"),
                result["frame_count"],
                result["still_fraction"],
                result.get("heat_note") or "",
                result.get("detector_note") or "",
                1 if result.get("accelerated", mode == "demo") else 0,
                result.get("playback") or ("frames" if mode == "demo" else "live"),
                ",".join(result.get("zones") or ["1", "2"]),
                ",".join(result.get("fault_zones") or []),
            ),
        )
        seen = set()
        for point in result["points"]:
            key = (point["zone"], point["cell"])
            seen.add(key)
            status, marked_by, marked_at = "pending", "", ""
            old = previous.get(key)
            if keep_marks and old is not None and old["status"] != "pending":
                status = old["status"]
                marked_by = old["marked_by"]
                marked_at = old["marked_at"]
            opened_at = ""
            if old is not None and old["opened_at"]:
                opened_at = old["opened_at"]
            elif point.get("opened_at"):
                opened_at = point["opened_at"]
            else:
                opened_at = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                """
                INSERT INTO points (
                    mode, zone, cell, t_min, t_label, delta_c, reason, cx_cm, cy_cm, track_id,
                    status, marked_by, marked_at, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mode,
                    point["zone"],
                    point["cell"],
                    point["t_min"],
                    point["t_label"],
                    point["delta_c"],
                    point["reason"],
                    point["cx_cm"],
                    point["cy_cm"],
                    point["track_id"],
                    status,
                    marked_by,
                    marked_at,
                    opened_at,
                ),
            )
        if keep_marks:
            for key, old in previous.items():
                if key in seen or old["status"] == "pending":
                    continue
                conn.execute(
                    """
                INSERT INTO points (
                    mode, zone, cell, t_min, t_label, delta_c, reason, cx_cm, cy_cm, track_id,
                    status, marked_by, marked_at, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mode,
                    old["zone"],
                    old["cell"],
                    old["t_min"],
                    old["t_label"],
                    old["delta_c"],
                    old["reason"],
                    old["cx_cm"],
                    old["cy_cm"],
                    old["track_id"],
                    old["status"],
                    old["marked_by"],
                    old["marked_at"],
                    old["opened_at"] or datetime.now().isoformat(timespec="seconds"),
                ),
            )
        conn.execute("UPDATE meta SET active_mode = ? WHERE id = 1", (mode,))
        conn.commit()
    conn.close()


def remember_hour(path: Path, mode: str, day: str, hour: int, fraction: float) -> None:
    conn = connect(path)
    with LOCK:
        conn.execute(
            """
            INSERT INTO activity_hour (mode, day, hour, fraction)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(mode, day, hour) DO UPDATE SET fraction = excluded.fraction
            """,
            (mode, day, hour, fraction),
        )
        conn.commit()
    conn.close()


def hour_fraction(path: Path, mode: str, day: str, hour: int) -> float | None:
    if not path.exists():
        return None
    conn = connect(path)
    row = conn.execute(
        "SELECT fraction FROM activity_hour WHERE mode = ? AND day = ? AND hour = ?",
        (mode, day, hour),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return float(row["fraction"])


def open_records(path: Path, mode: str, hours: float = 6) -> list[dict]:
    """Точки, которые уже открыты и шесть часов не дают вторую запись в ту же клетку."""
    if not path.exists():
        return []
    conn = connect(path)
    rows = conn.execute("SELECT * FROM points WHERE mode = ?", (mode,)).fetchall()
    conn.close()
    cutoff = datetime.now().timestamp() - hours * 3600
    fresh = []
    for row in rows:
        opened = row["opened_at"]
        if opened:
            try:
                stamp = datetime.fromisoformat(opened).timestamp()
            except ValueError:
                stamp = datetime.now().timestamp()
            if stamp < cutoff:
                continue
        fresh.append(dict(row))
    return fresh


def state(path: Path, mode: str | None = None) -> dict:
    if not path.exists():
        return _empty("demo")
    conn = connect(path)
    if mode is None:
        mode = conn.execute("SELECT active_mode FROM meta WHERE id = 1").fetchone()["active_mode"]
    run = conn.execute("SELECT * FROM runs WHERE mode = ?", (mode,)).fetchone()
    demo_ready = conn.execute("SELECT 1 FROM runs WHERE mode = 'demo'").fetchone() is not None
    live_ready = conn.execute("SELECT 1 FROM runs WHERE mode = 'live'").fetchone() is not None
    if run is None:
        conn.close()
        payload = _empty(mode)
        payload["demo_ready"] = demo_ready
        payload["live_ready"] = live_ready
        return payload
    points = [dict(row) for row in conn.execute("SELECT * FROM points WHERE mode = ? ORDER BY t_min, id", (mode,))]
    hours = [
        {"day": row["day"], "hour": int(row["hour"]), "fraction": round(float(row["fraction"]), 3)}
        for row in conn.execute(
            "SELECT day, hour, fraction FROM activity_hour WHERE mode = ? ORDER BY day, hour",
            (mode,),
        ).fetchall()
    ][-24:]
    conn.close()
    confirmed = sum(1 for point in points if point["status"] == "dead")
    pending = sum(1 for point in points if point["status"] == "pending")
    planted = int(run["planted"])
    visible = int(run["visible"])
    weight_hidden = bool(run["weight_hidden"])
    median = run["weight_median"]
    norm = run["weight_norm"]
    delta_pct = None
    if not weight_hidden and median is not None and norm:
        delta_pct = (median - norm) / norm * 100
    return {
        "ready": True,
        "mode": mode,
        "demo_ready": demo_ready,
        "live_ready": live_ready,
        "section": run["section"],
        "planted": planted,
        "visible": visible,
        "gap": planted - visible,
        "age_days": run["age_days"],
        "clock": run["clock"],
        "accelerated": bool(run["accelerated"]),
        "playback": run["playback"] or "frames",
        "heat_note": run["heat_note"] or "",
        "detector_note": run["detector_note"] or "",
        "weight": {
            "median": None if weight_hidden or median is None else round(median),
            "norm": None if norm is None else round(norm),
            "hidden": weight_hidden,
            "delta_pct": None if delta_pct is None else round(delta_pct, 1),
            "control": run["control_grams"],
        },
        "activity": {
            "text": run["activity_text"],
            "detail": run["activity_detail"],
            "phone": bool(run["phone"]),
            "still": None if run["still_fraction"] is None else round(float(run["still_fraction"]), 3),
        },
        "hours": hours,
        "thermal_fault": bool(run["thermal_fault"]),
        "fault_zones": [part for part in (run["fault_zones"] or "").split(",") if part],
        "deaths_confirmed": confirmed,
        "deaths_pending": pending,
        "frame_count": run["frame_count"],
        "zones": [part for part in (run["zones"] or "1,2").split(",") if part],
        "points": [{**point, "heat": f"−{point['delta_c']:.0f} °C"} for point in points],
    }


def _empty(mode: str) -> dict:
    return {
        "ready": False,
        "mode": mode,
        "demo_ready": False,
        "live_ready": False,
        "heat_note": "",
        "detector_note": "",
        "playback": "frames" if mode == "demo" else "live",
        "points": [],
    }


def mark_point(path: Path, point_id: int, status: str) -> dict:
    if status not in {"dead", "alive"}:
        raise ValueError("status")
    conn = connect(path)
    row = conn.execute("SELECT mode FROM points WHERE id = ?", (point_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError("point")
    label = "падаль" if status == "dead" else "живая"
    now = datetime.now().strftime("%H:%M")
    with LOCK:
        conn.execute(
            "UPDATE points SET status = ?, marked_by = ?, marked_at = ? WHERE id = ?",
            (status, "мастер", f"{label}, {now}", point_id),
        )
        conn.commit()
    mode = row["mode"]
    conn.close()
    return state(path, mode)


def update_flock(
    path: Path,
    mode: str,
    planted: int | None = None,
    control_grams: float | None = None,
    age_days: int | None = None,
) -> dict:
    conn = connect(path)
    run = conn.execute("SELECT * FROM runs WHERE mode = ?", (mode,)).fetchone()
    if run is None:
        conn.close()
        raise ValueError("empty")
    planted_value = int(planted) if planted is not None else int(run["planted"])
    age = int(age_days) if age_days is not None else int(run["age_days"])
    control = float(control_grams) if control_grams is not None else run["control_grams"]
    hidden = 1 if age < 5 or run["weight_median"] is None else 0
    with LOCK:
        conn.execute(
            """
            UPDATE runs
            SET planted = ?, age_days = ?, control_grams = ?, weight_hidden = ?, weight_norm = ?
            WHERE mode = ?
            """,
            (planted_value, age, control, hidden, norm_grams(age), mode),
        )
        conn.commit()
    conn.close()
    return state(path, mode)
