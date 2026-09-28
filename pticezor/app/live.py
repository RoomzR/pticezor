"""Локальные камеры. В правила уходит один кадр в секунду, часы настоящие."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from app.detect import TrackerSession, find_gap_spots, sample_floor
from app.ingest import gray_to_thermal, is_night
from app.pipeline import GENERATED, WEIGHTS
from app.rules import (
    DeathPoint,
    Detection,
    Frame,
    GapSpot,
    Grid,
    ZoneRect,
    activity_report,
    any_thermal_fault,
    thermal_fault,
    clock_label,
    exclusive_counts,
    find_deaths,
    fit_demo_model,
    median_weight,
    norm_grams,
)
from app.scenario import HEIGHT, WIDTH, WORLD_H, WORLD_W
from app.store import hour_fraction, open_records, remember_hour, save_run

GRID = Grid()
LIVE_DIR = GENERATED / "live"


def list_cameras(limit: int = 8) -> list[dict]:
    found = []
    for index in range(limit):
        cap = cv2.VideoCapture(index)
        try:
            if not cap.isOpened():
                continue
            ok, _frame = cap.read()
            if ok:
                found.append({"index": index, "label": f"Камера {index}"})
        except cv2.error:
            continue
        finally:
            cap.release()
    return found


class LiveSession:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.error = ""
        self.running = False
        self.line_on = False
        self._seen_cells: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def set_line(self, on: bool) -> None:
        with self._lock:
            if on and not self.line_on:
                self._seen_cells = {}
            self.line_on = on

    def start(self, config: dict) -> None:
        self.stop()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.error = ""
        self.line_on = bool(config.get("line_on"))
        self._seen_cells = {}
        self._thread = threading.Thread(target=self._loop, args=(config, self._stop), daemon=True)
        self.running = True
        self._thread.start()
        self._ready.wait(timeout=4)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        self.running = False

    def _loop(self, config: dict, stop: threading.Event) -> None:
        caps = []
        try:
            zones = [zone for zone in config["zones"] if zone.get("rgb") is not None]
            if not zones:
                self.error = "Не выбрана обычная камера."
                return
            opened = []
            for zone in zones:
                rgb = cv2.VideoCapture(int(zone["rgb"]))
                thermal = None
                if zone.get("thermal") is not None:
                    thermal = cv2.VideoCapture(int(zone["thermal"]))
                    if not thermal.isOpened():
                        thermal.release()
                        thermal = None
                        self.error = f"Тепловизор {zone['thermal']} не открылся. Обычная камера зоны {zone['id']} идёт без точек падежа."
                if not rgb.isOpened():
                    rgb.release()
                    self.error = f"Камера {zone['rgb']} не открылась."
                    return
                opened.append((str(zone["id"]), rgb, thermal))
                caps.append(rgb)
                if thermal is not None:
                    caps.append(thermal)
            self._run(opened, config, stop)
        except Exception as exc:
            self.error = str(exc)
        finally:
            for cap in caps:
                cap.release()
            self.running = False
            self._ready.set()

    def _run(self, opened, config: dict, stop: threading.Event) -> None:
        px_per_cm = float(config["feeder_px"]) / max(float(config["feeder_cm"]), 1.0)
        model = fit_demo_model()
        trackers = {zone_id: TrackerSession(WEIGHTS if WEIGHTS.exists() else None) for zone_id, _rgb, _th in opened}
        stamped: list[tuple[datetime, Frame]] = []
        last_boxes: dict[str, list[Detection]] = {}
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        self._ready.set()
        pan = _pan_polygon(float(config["feeder_px"])) if config.get("mask_pan", True) else None
        while not stop.wait(1.0):
            now = datetime.now()
            t_min = now.hour * 60 + now.minute + now.second / 60.0
            night = is_night(now.hour, int(config["night_from"]), int(config["night_to"]))
            with self._lock:
                line_on = self.line_on
            saw_heat = False
            for zone_id, rgb, thermal_cap in opened:
                ok, frame = rgb.read()
                if not ok:
                    self.error = f"Камера зоны {zone_id} перестала отдавать кадр."
                    continue
                frame = cv2.resize(frame, (WIDTH, HEIGHT))
                if thermal_cap is not None:
                    tok, tframe = thermal_cap.read()
                    thermal = gray_to_thermal(tframe) if tok else np.full((120, 160), 24.0, np.float32)
                    heat = "sensor" if tok else "none"
                else:
                    thermal = np.full((120, 160), 24.0, np.float32)
                    heat = "none"
                boxes = trackers[zone_id].step(frame, [pan] if pan is not None else [])
                if pan is not None:
                    boxes = [box for box in boxes if cv2.pointPolygonTest(pan, (box.cx, box.cy), False) < 0]
                thermal_full = cv2.resize(thermal, (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST)
                detections = []
                for box in boxes:
                    det = Detection(
                        track_id=box.track_id,
                        cx_cm=box.cx / px_per_cm,
                        cy_cm=box.cy / px_per_cm,
                        w_cm=max(box.w, 1) / px_per_cm,
                        h_cm=max(box.h, 1) / px_per_cm,
                        temp_c=_center_temp(thermal_full, box),
                        merged=box.merged,
                        edge=box.edge,
                        zone=zone_id,
                    )
                    detections.append(det)
                    cv2.rectangle(frame, (int(box.x1), int(box.y1)), (int(box.x2), int(box.y2)), (52, 58, 30), 2)
                if pan is not None:
                    cv2.polylines(frame, [pan], True, (90, 110, 140), 2)
                cv2.imwrite(str(LIVE_DIR / f"zone{zone_id}.jpg"), frame)
                if heat == "sensor":
                    saw_heat = True
                    floor = sample_floor(thermal_full, boxes)
                    gaps = find_gap_spots(
                        thermal_full,
                        boxes,
                        [det.temp_c for det in detections],
                        [pan] if pan is not None else [],
                        floor,
                    )
                    gap_spots = [
                        GapSpot(px / px_per_cm, py / px_per_cm, temp, zone_id) for px, py, temp in gaps
                    ]
                else:
                    floor = 24.0
                    gap_spots = []
                current_cells = {GRID.cell(det.cx_cm, det.cy_cm) for det in detections}
                occluded: list[str] = []
                if line_on:
                    seen = self._seen_cells.setdefault(zone_id, set())
                    occluded = sorted(seen - current_cells)
                    seen |= current_cells
                stamped.append(
                    (
                        now,
                        Frame(
                            t_min=t_min,
                            night=night,
                            detections=detections,
                            floor_temp_c=floor,
                            floor_baseline_c=24.0,
                            feeder_on=line_on,
                            occluded_cells=occluded,
                            gap_spots=gap_spots,
                            zone=zone_id,
                            width_cm=WORLD_W,
                            height_cm=WORLD_H,
                        ),
                    )
                )
                last_boxes[zone_id] = detections
            cutoff = now - timedelta(minutes=20)
            stamped = [(moment, frame) for moment, frame in stamped if moment >= cutoff]
            self._publish([frame for _moment, frame in stamped], last_boxes, opened, config, model, now, saw_heat)

    def _publish(self, history, last_boxes, opened, config, model, now: datetime, saw_heat: bool) -> None:
        stored = open_records(self.db_path, "live")
        existing = [
            DeathPoint(
                zone=row["zone"],
                cell=row["cell"],
                t_min=float(row["t_min"]),
                delta_c=float(row["delta_c"]),
                reason=row["reason"] or "hold",
                cx_cm=float(row["cx_cm"] or 0),
                cy_cm=float(row["cy_cm"] or 0),
                track_id=row["track_id"],
            )
            for row in stored
        ]
        points = keep_recent(find_deaths(history, GRID, existing), stored) if saw_heat else []
        usable = []
        world = []
        for index, (zone_id, _rgb, _th) in enumerate(opened):
            offset = index * WORLD_W
            for det in last_boxes.get(zone_id, []):
                usable.append(det)
                world.append((det.cx_cm + offset, det.cy_cm))
        zones = [
            ZoneRect(zone_id, index * WORLD_W, 0, (index + 1) * WORLD_W, WORLD_H, index)
            for index, (zone_id, _r, _t) in enumerate(opened)
        ]
        visible = int(sum(exclusive_counts(world, zones).values())) if zones else 0
        age = int(config["age_days"])
        weight = median_weight(usable, age, model)
        yesterday_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday = hour_fraction(self.db_path, "live", yesterday_day, now.hour)
        activity = activity_report(history, yesterday, age)
        text = activity.text
        phone = activity.phone
        if yesterday is None and age > 1:
            text = "за этот час ещё не с чем сравнить"
            phone = False
        remember_hour(self.db_path, "live", now.strftime("%Y-%m-%d"), now.hour, activity.still_fraction)
        if saw_heat:
            heat_note = "Тепло читается с выбранной камеры по яркости кадра."
        else:
            heat_note = "Тепловизор не выбран, точки падежа не открываются."
        detector = ""
        if not WEIGHTS.exists():
            detector = "Рамки по контрасту. Настоящие рамки птицы появятся после файла weights/birds.pt."
        result = {
            "section": "секция",
            "planted": int(config["planted"]),
            "age_days": age,
            "visible": visible,
            "clock": clock_label(now.hour * 60 + now.minute),
            "weight_median": weight,
            "weight_norm": norm_grams(age),
            "weight_hidden": weight is None,
            "activity_text": text,
            "activity_detail": activity.detail,
            "phone": phone,
            "still_fraction": activity.still_fraction,
            "thermal_fault": any_thermal_fault(history) if saw_heat else False,
            "fault_zones": sorted({frame.zone for frame in history if thermal_fault(frame)}) if saw_heat else [],
            "frame_count": 1,
            "points": [
                {
                    "zone": point.zone,
                    "cell": point.cell,
                    "t_min": point.t_min,
                    "t_label": clock_label(point.t_min),
                    "delta_c": round(point.delta_c, 1),
                    "reason": point.reason,
                    "cx_cm": point.cx_cm,
                    "cy_cm": point.cy_cm,
                    "track_id": point.track_id,
                    "opened_at": next(
                        (
                            row["opened_at"]
                            for row in stored
                            if row["zone"] == point.zone and row["cell"] == point.cell
                        ),
                        "",
                    ),
                }
                for point in points
            ],
            "heat_note": heat_note,
            "detector_note": detector,
            "accelerated": False,
            "playback": "live",
            "zones": [zone_id for zone_id, _rgb, _thermal in opened],
        }
        save_run(self.db_path, result, "live", keep_marks=True)


def keep_recent(found: list[DeathPoint], stored: list[dict]) -> list[DeathPoint]:
    """Уже открытая клетка остаётся в списке и не заводится второй раз."""
    keys = {(point.zone, point.cell) for point in found}
    for row in stored:
        key = (row["zone"], row["cell"])
        if key in keys:
            continue
        found.append(
            DeathPoint(
                zone=row["zone"],
                cell=row["cell"],
                t_min=float(row["t_min"]),
                delta_c=float(row["delta_c"]),
                reason=row["reason"] or "hold",
                cx_cm=float(row["cx_cm"] or 0),
                cy_cm=float(row["cy_cm"] or 0),
                track_id=row["track_id"],
            )
        )
        keys.add(key)
    return found


def _pan_polygon(feeder_px: float) -> np.ndarray:
    pan_w = max(48.0, float(feeder_px) * 0.25)
    pan_h = max(32.0, float(feeder_px) * 0.17)
    x1 = WIDTH / 2 - pan_w / 2
    y1 = HEIGHT - pan_h - 16
    return np.array(
        [
            [int(x1), int(y1)],
            [int(x1 + pan_w), int(y1)],
            [int(x1 + pan_w), int(y1 + pan_h)],
            [int(x1), int(y1 + pan_h)],
        ],
        dtype=np.int32,
    )


def _center_temp(thermal: np.ndarray, box) -> float:
    cx = int(round(box.cx))
    cy = int(round(box.cy))
    y1 = max(0, cy - 1)
    y2 = min(thermal.shape[0], cy + 2)
    x1 = max(0, cx - 1)
    x2 = min(thermal.shape[1], cx + 2)
    patch = thermal[y1:y2, x1:x2]
    if patch.size == 0:
        return 24.0
    return float(np.median(patch))
