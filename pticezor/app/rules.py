"""Правила падежа, веса, активности и счёта. Разделы 4.3–4.6 заявки."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

import numpy as np
from sklearn.linear_model import LinearRegression

COLD_DELTA_C = 4.0
POSE_SIDE = 2.0
POSE_SIT = 1.8
STILL_CM = 5.0
BBOX_CHANGE = 0.10
HOLD_MIN = 10.0
DAY_WINDOW_MIN = 15.0
DEDUP_MIN = 6 * 60.0
RECHECK_MIN = 15.0
STILL_FLOCK = 0.85
FAULT_SHARE = 0.40
FAULT_MIN_BIRDS = 3
TRACK_GAP_MIN = 1.5
WALL_SHARE = 0.50
ACTIVITY_PP = 15.0

# Учебная кривая для экрана. Это не взвешивание хозяйства.
NORM_TABLE = (
    (0, 42),
    (7, 189),
    (14, 480),
    (21, 943),
    (28, 1524),
    (35, 2192),
    (42, 2906),
)


@dataclass
class Detection:
    track_id: int | None
    cx_cm: float
    cy_cm: float
    w_cm: float
    h_cm: float
    temp_c: float
    merged: bool = False
    edge: bool = False
    zone: str = "1"


@dataclass
class GapSpot:
    cx_cm: float
    cy_cm: float
    temp_c: float
    zone: str = "1"


@dataclass
class Frame:
    t_min: float
    night: bool
    detections: list[Detection]
    floor_temp_c: float
    floor_baseline_c: float = 24.0
    feeder_on: bool = False
    occluded_cells: list[str] = field(default_factory=list)
    gap_spots: list[GapSpot] = field(default_factory=list)
    zone: str = "1"
    width_cm: float = 480.0
    height_cm: float = 270.0


@dataclass
class Grid:
    x0: float = 0.0
    y0: float = 0.0
    cell_w: float = 160.0
    cell_h: float = 67.5
    col_labels: tuple[str, ...] = ("1", "2", "3")
    row_labels: tuple[str, ...] = ("А", "Б", "В", "Г")

    def cell(self, x: float, y: float) -> str:
        col = int((x - self.x0) / self.cell_w)
        row = int((y - self.y0) / self.cell_h)
        col = min(max(col, 0), len(self.col_labels) - 1)
        row = min(max(row, 0), len(self.row_labels) - 1)
        return f"{self.row_labels[row]}{self.col_labels[col]}"


@dataclass
class DeathPoint:
    zone: str
    cell: str
    t_min: float
    delta_c: float
    reason: str
    cx_cm: float
    cy_cm: float
    track_id: int | None = None


@dataclass
class ZoneRect:
    id: str
    x0: float
    y0: float
    x1: float
    y1: float
    priority: int


@dataclass
class ActivityReport:
    text: str
    detail: str
    phone: bool
    still_fraction: float


@dataclass
class _Sample:
    t: float
    cx: float
    cy: float
    w: float
    h: float
    temp: float
    pose: str
    cold: bool
    merged: bool
    zone: str
    cell: str
    night: bool
    delta: float
    track_id: int


def pose_label(w_cm: float, h_cm: float) -> str:
    short = min(w_cm, h_cm)
    if short <= 1e-6:
        return "undecided"
    aspect = max(w_cm, h_cm) / short
    if aspect >= POSE_SIDE:
        return "side"
    if aspect < POSE_SIT:
        return "sit"
    return "undecided"


def norm_grams(age_days: float) -> float:
    if age_days <= NORM_TABLE[0][0]:
        return float(NORM_TABLE[0][1])
    if age_days >= NORM_TABLE[-1][0]:
        return float(NORM_TABLE[-1][1])
    for (a0, g0), (a1, g1) in zip(NORM_TABLE, NORM_TABLE[1:]):
        if a0 <= age_days <= a1:
            k = (age_days - a0) / (a1 - a0)
            return float(g0 + (g1 - g0) * k)
    return float(NORM_TABLE[-1][1])


def fit_demo_model() -> LinearRegression:
    """Линейная модель на фиксированной демо-таблице кросса, не на хозяйстве."""
    rng = np.random.default_rng(0)
    features: list[list[float]] = []
    target: list[float] = []
    for age in range(7, 36):
        base_w = 6 + age * 0.45
        base_h = 4 + age * 0.22
        for _ in range(6):
            w = base_w * float(rng.uniform(0.88, 1.12))
            h = base_h * float(rng.uniform(0.88, 1.12))
            area = w * h
            grams = 18 * w + 22 * h + 1.1 * area + 28 * age
            features.append([w, h, area, float(age)])
            target.append(grams)
    model = LinearRegression()
    model.fit(np.asarray(features), np.asarray(target))
    return model


def usable_for_weight(det: Detection) -> bool:
    return not det.edge and not det.merged and det.w_cm > 0 and det.h_cm > 0


def median_weight(dets: list[Detection], age_days: int, model: LinearRegression) -> float | None:
    if age_days < 5:
        return None
    rows = [
        [d.w_cm, d.h_cm, d.w_cm * d.h_cm, float(age_days)]
        for d in dets
        if usable_for_weight(d)
    ]
    if not rows:
        return None
    pred = model.predict(np.asarray(rows, dtype=float))
    return float(np.median(pred))


def point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def in_any_mask(x: float, y: float, masks: list[list[tuple[float, float]]]) -> bool:
    return any(point_in_poly(x, y, poly) for poly in masks)


def _neighbor_median(dets: list[Detection], index: int) -> float | None:
    others = [d.temp_c for i, d in enumerate(dets) if i != index]
    if not others:
        return None
    return float(statistics.median(others))


def thermal_fault(frame: Frame) -> bool:
    dets = frame.detections
    if len(dets) < FAULT_MIN_BIRDS:
        return False
    cold = 0
    for i, det in enumerate(dets):
        med = _neighbor_median(dets, i)
        if med is not None and det.temp_c <= med - COLD_DELTA_C:
            cold += 1
    many = cold >= FAULT_MIN_BIRDS and cold / len(dets) >= FAULT_SHARE
    floor_cold = frame.floor_temp_c <= frame.floor_baseline_c - COLD_DELTA_C
    return many and floor_cold


def zone_of(x: float, y: float, zones: list[ZoneRect]) -> str | None:
    hits = [z for z in zones if z.x0 <= x < z.x1 and z.y0 <= y < z.y1]
    if not hits:
        return None
    return min(hits, key=lambda z: z.priority).id


def exclusive_counts(points: list[tuple[float, float]], zones: list[ZoneRect]) -> dict[str, int]:
    counts = {z.id: 0 for z in zones}
    for x, y in points:
        owner = zone_of(x, y, zones)
        if owner is not None:
            counts[owner] += 1
    return counts


def _displacement(samples: list[_Sample], t0: float, t1: float) -> float:
    window = [s for s in samples if t0 - 1e-9 <= s.t <= t1 + 1e-9]
    if len(window) < 2:
        return 0.0
    return math.hypot(window[-1].cx - window[0].cx, window[-1].cy - window[0].cy)


def _bbox_change(samples: list[_Sample], t0: float, t1: float) -> float:
    window = [s for s in samples if t0 - 1e-9 <= s.t <= t1 + 1e-9]
    if len(window) < 2:
        return 0.0
    w0, h0 = window[0].w, window[0].h
    w1, h1 = window[-1].w, window[-1].h
    if w0 <= 1e-6 or h0 <= 1e-6:
        return 1.0
    return max(abs(w1 - w0) / w0, abs(h1 - h0) / h0)


def _still_fraction(hist: dict[int, list[_Sample]], present: set[int], t: float) -> float:
    if not present:
        return 0.0
    still = 0
    for tid in present:
        if _displacement(hist[tid], t - DAY_WINDOW_MIN, t) < STILL_CM:
            still += 1
    return still / len(present)


def _open_ok(opened: list[DeathPoint], existing: list[DeathPoint], zone: str, cell: str, t: float) -> bool:
    for point in [*existing, *opened]:
        if point.zone == zone and point.cell == cell and abs(point.t_min - t) <= DEDUP_MIN:
            return False
    return True


def find_deaths(
    frames: list[Frame],
    grid: Grid,
    existing: list[DeathPoint] | None = None,
) -> list[DeathPoint]:
    existing = list(existing or [])
    by_zone: dict[str, list[Frame]] = {}
    for frame in frames:
        by_zone.setdefault(frame.zone, []).append(frame)
    opened: list[DeathPoint] = []
    for zone_frames in by_zone.values():
        opened.extend(_deaths_one_zone(zone_frames, grid, existing + opened))
    return opened


def _deaths_one_zone(frames: list[Frame], grid: Grid, existing: list[DeathPoint]) -> list[DeathPoint]:
    opened: list[DeathPoint] = []
    hist: dict[int, list[_Sample]] = {}
    pending_cells: set[str] = set()
    feeder_seen_on = False
    feeder_off_at: float | None = None

    for frame in frames:
        fault = thermal_fault(frame)
        if frame.feeder_on:
            feeder_seen_on = True
            feeder_off_at = None
            pending_cells.update(frame.occluded_cells)
        elif feeder_seen_on and feeder_off_at is None:
            feeder_off_at = frame.t_min
            feeder_seen_on = False

        present: set[int] = set()
        for index, det in enumerate(frame.detections):
            if det.track_id is None:
                continue
            present.add(det.track_id)
            med = _neighbor_median(frame.detections, index)
            cold = (
                not fault
                and med is not None
                and det.temp_c <= med - COLD_DELTA_C
            )
            delta = 0.0 if med is None else med - det.temp_c
            sample = _Sample(
                t=frame.t_min,
                cx=det.cx_cm,
                cy=det.cy_cm,
                w=det.w_cm,
                h=det.h_cm,
                temp=det.temp_c,
                pose=pose_label(det.w_cm, det.h_cm),
                cold=cold,
                merged=det.merged,
                zone=frame.zone,
                cell=grid.cell(det.cx_cm, det.cy_cm),
                night=frame.night,
                delta=delta,
                track_id=det.track_id,
            )
            track = hist.setdefault(det.track_id, [])
            if track and frame.t_min - track[-1].t > TRACK_GAP_MIN:
                track.clear()
            track.append(sample)

        still_frac = _still_fraction(hist, present, frame.t_min)

        if not fault:
            bird_temps = [d.temp_c for d in frame.detections]
            if bird_temps:
                med_all = float(statistics.median(bird_temps))
                for gap in frame.gap_spots:
                    if gap.temp_c <= med_all - COLD_DELTA_C:
                        cell = grid.cell(gap.cx_cm, gap.cy_cm)
                        if _open_ok(opened, existing, frame.zone, cell, frame.t_min):
                            opened.append(
                                DeathPoint(
                                    zone=frame.zone,
                                    cell=cell,
                                    t_min=frame.t_min,
                                    delta_c=med_all - gap.temp_c,
                                    reason="gap",
                                    cx_cm=gap.cx_cm,
                                    cy_cm=gap.cy_cm,
                                )
                            )

            for tid in present:
                track = hist[tid]
                if _streak_minutes(track) + 1e-6 < HOLD_MIN:
                    continue
                last = track[-1]
                if not _day_ok(track, last, still_frac):
                    continue
                if _open_ok(opened, existing, last.zone, last.cell, last.t):
                    opened.append(
                        DeathPoint(
                            zone=last.zone,
                            cell=last.cell,
                            t_min=last.t,
                            delta_c=last.delta,
                            reason="hold",
                            cx_cm=last.cx,
                            cy_cm=last.cy,
                            track_id=last.track_id,
                        )
                    )

        if (
            feeder_off_at is not None
            and frame.t_min + 1e-6 >= feeder_off_at + RECHECK_MIN
            and not fault
        ):
            for cell in list(pending_cells):
                for det in frame.detections:
                    if det.merged or det.track_id is None:
                        continue
                    if grid.cell(det.cx_cm, det.cy_cm) != cell:
                        continue
                    if pose_label(det.w_cm, det.h_cm) != "side":
                        continue
                    med = _neighbor_median(frame.detections, frame.detections.index(det))
                    if med is None or det.temp_c > med - COLD_DELTA_C:
                        continue
                    if _open_ok(opened, existing, frame.zone, cell, frame.t_min):
                        opened.append(
                            DeathPoint(
                                zone=frame.zone,
                                cell=cell,
                                t_min=frame.t_min,
                                delta_c=med - det.temp_c,
                                reason="recheck",
                                cx_cm=det.cx_cm,
                                cy_cm=det.cy_cm,
                                track_id=det.track_id,
                            )
                        )
                    break
            pending_cells.clear()
            feeder_off_at = None

    return opened


def _streak_minutes(track: list[_Sample]) -> float:
    last = track[-1]
    if not last.cold or last.merged or last.pose != "side":
        return 0.0
    i = len(track) - 1
    while i >= 0 and track[i].cold and track[i].pose == "side" and not track[i].merged:
        i -= 1
    return last.t - track[i + 1].t


def _day_ok(track: list[_Sample], last: _Sample, still_frac: float) -> bool:
    if last.night:
        return True
    if still_frac >= STILL_FLOCK:
        return False
    t0 = last.t - DAY_WINDOW_MIN
    if _displacement(track, t0, last.t) >= STILL_CM:
        return False
    if _bbox_change(track, t0, last.t) >= BBOX_CHANGE:
        return False
    return True


def _histories(frames: list[Frame]) -> dict[int, list[_Sample]]:
    hist: dict[int, list[_Sample]] = {}
    for frame in frames:
        for det in frame.detections:
            if det.track_id is None:
                continue
            sample = _Sample(
                t=frame.t_min,
                cx=det.cx_cm,
                cy=det.cy_cm,
                w=det.w_cm,
                h=det.h_cm,
                temp=det.temp_c,
                pose=pose_label(det.w_cm, det.h_cm),
                cold=False,
                merged=det.merged,
                zone=frame.zone,
                cell="",
                night=frame.night,
                delta=0.0,
                track_id=det.track_id,
            )
            hist.setdefault((frame.zone, det.track_id), []).append(sample)
    return hist


def activity_report(frames: list[Frame], yesterday_still: float | None, age_days: int) -> ActivityReport:
    hist = _histories(frames)
    if not hist or not frames:
        return ActivityReport("нет кадров за этот час", "", False, 0.0)
    last_t = frames[-1].t_min
    first_t = frames[0].t_min
    present = set(hist)
    still = 0
    for tid, samples in hist.items():
        if _displacement(samples, first_t, last_t) < STILL_CM:
            still += 1
    frac = still / len(present)
    shares = _grid_shares(frames)
    wall = max(shares) >= WALL_SHARE if shares else False
    first_day = age_days <= 1 or yesterday_still is None
    if first_day:
        text = "первые сутки, сравнивать не с чем"
        phone = False
    else:
        delta_pp = (frac - yesterday_still) * 100
        if delta_pp > ACTIVITY_PP:
            text = "ниже обычной"
            phone = True
        elif wall:
            text = "птица собралась у стены"
            phone = True
        else:
            text = "в пределах обычного для этого часа"
            phone = False
    detail = f"замершие {frac * 100:.0f}%"
    if yesterday_still is not None and not first_day:
        detail += f", вчера в этот час {yesterday_still * 100:.0f}%"
    if wall and text == "ниже обычной":
        detail += ", птица собралась к краю кадра"
    return ActivityReport(text, detail, phone, frac)


def _grid_shares(frames: list[Frame]) -> list[float]:
    """Доля птицы по сетке 3×3 отдельно в каждой зоне. Стена — клетка кроме центра."""
    if not frames:
        return []
    shares: list[float] = []
    zones = {frame.zone for frame in frames}
    for zone in zones:
        zone_frames = [frame for frame in frames if frame.zone == zone]
        last = zone_frames[-1]
        bins = [0] * 9
        counted = 0
        for det in last.detections:
            if det.track_id is None:
                continue
            col = min(2, max(0, int(det.cx_cm / last.width_cm * 3)))
            row = min(2, max(0, int(det.cy_cm / last.height_cm * 3)))
            bins[row * 3 + col] += 1
            counted += 1
        if counted == 0:
            continue
        shares.extend(bins[i] / counted for i in range(9) if i != 4)
    return shares


def any_thermal_fault(frames: list[Frame]) -> bool:
    return any(thermal_fault(frame) for frame in frames)


def clock_label(t_min: float) -> str:
    minute = int(round(t_min))
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}"
