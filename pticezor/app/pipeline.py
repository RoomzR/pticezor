"""Разбор ролика: рамки, тепло, правила, кадры с подсветкой."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.detect import (
    find_gap_spots,
    sample_center,
    sample_floor,
    track_video,
    upsample_thermal,
)
from app.rules import (
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
from app.scenario import HEIGHT, WIDTH, DemoClip, build_demo

GRID = Grid()
ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "weights" / "birds.pt"
GENERATED = ROOT / "demo" / "generated"


def analyze(clip: DemoClip) -> dict:
    model = fit_demo_model()
    rules_frames: list[Frame] = []
    last_boxes: dict[str, list] = {}
    track_last: dict[tuple[str, int], Detection] = {}
    zone_meta = []

    for zone in clip.zones:
        masks = [zone.pan_px]
        mask_tuples = [[(float(x), float(y)) for x, y in zone.pan_px]]
        tracked = track_video(zone.detect_frames, masks, WEIGHTS if WEIGHTS.exists() else None)
        zone_frames: list[Frame] = []
        for index, boxes in enumerate(tracked):
            thermal = upsample_thermal(zone.thermal[index], WIDTH, HEIGHT)
            kept = []
            temps = []
            for box in boxes:
                if _center_in_pan(box.cx, box.cy, zone.pan_px):
                    continue
                temp = sample_center(thermal, box)
                kept.append(box)
                temps.append(temp)
            floor = sample_floor(thermal, kept)
            detections = []
            for box, temp in zip(kept, temps):
                det = Detection(
                    track_id=box.track_id,
                    cx_cm=box.cx / zone.px_per_cm,
                    cy_cm=box.cy / zone.px_per_cm,
                    w_cm=box.w / zone.px_per_cm,
                    h_cm=box.h / zone.px_per_cm,
                    temp_c=temp,
                    merged=box.merged,
                    edge=box.edge,
                    zone=zone.zone_id,
                )
                detections.append(det)
                track_last[(zone.zone_id, box.track_id)] = det
            if zone.heat_mode == "teaching":
                _cool_longest(detections)
            gap_spots = []
            if zone.heat_mode == "sensor":
                gaps_px = find_gap_spots(thermal, kept, [d.temp_c for d in detections], masks, floor)
                gap_spots = [
                    GapSpot(px / zone.px_per_cm, py / zone.px_per_cm, temp, zone.zone_id)
                    for px, py, temp in gaps_px
                    if not _center_in_pan(px, py, zone.pan_px)
                ]
            zone_frames.append(
                Frame(
                    t_min=zone.times[index],
                    night=zone.nights[index],
                    detections=detections,
                    floor_temp_c=floor,
                    floor_baseline_c=clip.floor_baseline_c,
                    feeder_on=zone.feeder_on[index],
                    gap_spots=gap_spots,
                    zone=zone.zone_id,
                    width_cm=zone.width_cm,
                    height_cm=zone.height_cm,
                )
            )
        rules_frames.extend(zone_frames)
        last_boxes[zone.zone_id] = zone_frames[-1].detections if zone_frames else []
        zone_meta.append(zone)

    points = find_deaths(rules_frames, GRID)
    weight = median_weight(list(track_last.values()), clip.age_days, model)
    activity = activity_report(rules_frames, clip.yesterday_still, clip.age_days)
    zones = [
        ZoneRect(zone.zone_id, zone.world_x0, 0, zone.world_x0 + zone.width_cm, zone.height_cm, index)
        for index, zone in enumerate(zone_meta)
    ]
    world_points = []
    birds = []
    for zone in zone_meta:
        for det in last_boxes.get(zone.zone_id, []):
            world_points.append((det.cx_cm + zone.world_x0, det.cy_cm))
            birds.append(
                {
                    "zone": zone.zone_id,
                    "x": det.cx_cm / zone.width_cm,
                    "y": det.cy_cm / zone.height_cm,
                }
            )
    counts = exclusive_counts(world_points, zones)
    visible = int(sum(counts.values()))
    clock = clock_label(rules_frames[-1].t_min) if rules_frames else "00:00"
    return {
        "section": clip.section,
        "planted": clip.planted,
        "age_days": clip.age_days,
        "visible": visible,
        "clock": clock,
        "weight_median": weight,
        "weight_norm": norm_grams(clip.age_days),
        "weight_hidden": weight is None,
        "activity_text": activity.text,
        "activity_detail": activity.detail,
        "phone": activity.phone,
        "still_fraction": activity.still_fraction,
        "thermal_fault": any_thermal_fault(rules_frames),
        "fault_zones": sorted({frame.zone for frame in rules_frames if thermal_fault(frame)}),
        "frame_count": len(zone_meta[0].times) if zone_meta else 0,
        "times": zone_meta[0].times if zone_meta else [],
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
                "status": "pending",
                "marked_by": "",
                "marked_at": "",
            }
            for point in points
        ],
        "birds": birds,
        "zone_counts": counts,
        "heat_note": clip.heat_note,
        "detector_note": clip.detector_note,
        "accelerated": clip.accelerated,
        "playback": clip.playback,
        "had_yesterday": clip.yesterday_still is not None,
        "zones": [zone.zone_id for zone in zone_meta],
    }


def _cool_longest(detections: list[Detection]) -> None:
    if len(detections) < 2:
        return
    host = max(detections, key=lambda det: max(det.w_cm, det.h_cm) / max(min(det.w_cm, det.h_cm), 1e-6))
    others = [det.temp_c for det in detections if det is not host]
    host.temp_c = float(np.median(others)) - 5.0


def note_without_yesterday(result: dict) -> dict:
    if result.get("had_yesterday") or result.get("age_days", 0) <= 1:
        return result
    if "первые сутки" in result.get("activity_text", ""):
        result["activity_text"] = "за этот час ещё не с чем сравнить"
        result["phone"] = False
    return result


def write_frames(clip: DemoClip, result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    points = result["points"]
    for zone in clip.zones:
        folder = out_dir / f"zone{zone.zone_id}"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.jpg"):
            old.unlink()
        masks = [zone.pan_px]
        tracked = track_video(zone.detect_frames, masks, WEIGHTS if WEIGHTS.exists() else None)
        for index, (show, boxes) in enumerate(zip(zone.show_frames, tracked)):
            image = show.copy()
            t_min = zone.times[index]
            for box in boxes:
                color = (52, 58, 30)
                cv2.rectangle(image, (int(box.x1), int(box.y1)), (int(box.x2), int(box.y2)), color, 2)
                cv2.putText(
                    image,
                    str(box.track_id),
                    (int(box.x1), max(16, int(box.y1) - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            for point in points:
                if point["zone"] != zone.zone_id or t_min + 1e-6 < point["t_min"]:
                    continue
                cx = int(round(point["cx_cm"] * zone.px_per_cm))
                cy = int(round(point["cy_cm"] * zone.px_per_cm))
                cv2.circle(image, (cx, cy), 16, (47, 59, 142), 3)
            cv2.imwrite(str(folder / f"{index:05d}.jpg"), image, [int(cv2.IMWRITE_JPEG_QUALITY), 86])


BUILTIN_NOTE = (
    "Тепло на этом ролике — канал для проверки правила, тепловизора в зале нет. "
    "Вес обучен на демо-таблице кросса, не на хозяйстве. Время ролика ускорено: "
    "кадр раз в полминуты зала."
)


def process_demo(out_dir: Path | None = None) -> dict:
    clip = build_demo()
    clip.heat_note = BUILTIN_NOTE
    clip.accelerated = True
    target = out_dir or (GENERATED / "demo")
    result = analyze(clip)
    write_frames(clip, result, target)
    return result


def _center_in_pan(x: float, y: float, pan: np.ndarray) -> bool:
    return cv2.pointPolygonTest(pan, (float(x), float(y)), False) >= 0
