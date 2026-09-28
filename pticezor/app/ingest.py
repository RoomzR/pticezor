"""Свой ролик: кадры из файла, без подмены тепла, пока её не включили явно."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.scenario import HEIGHT, THERMAL_H, THERMAL_W, WIDTH, WORLD_W, DemoClip, ZoneClip

OFF_PAN = np.array([[-12, -12], [-8, -12], [-8, -8], [-12, -8]], dtype=np.int32)


def gray_to_thermal(frame_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (THERMAL_W, THERMAL_H), interpolation=cv2.INTER_AREA)
    return (16.0 + small.astype(np.float32) / 255.0 * 24.0).astype(np.float32)


def is_night(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _sample_indices(count: int, fps: float, hall_seconds: float, limit: int = 80) -> list[int]:
    if count <= 1:
        return [0]
    duration = count / max(fps, 1.0)
    hall = duration * hall_seconds
    want = int(min(limit, max(8, hall / 15.0)))
    want = min(want, count)
    if want <= 1:
        return [0, count - 1]
    return sorted({int(round(i)) for i in np.linspace(0, count - 1, want)})


def _read_sampled(path: Path, hall_seconds: float) -> tuple[list[np.ndarray], list[float], float]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("файл не открывается")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames: list[np.ndarray] = []
    times: list[float] = []
    if count <= 1:
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise ValueError("в файле нет кадров")
        return [_fit(frame)], [8 * 60.0], fps
    for index in _sample_indices(count, fps, hall_seconds):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            continue
        frames.append(_fit(frame))
        file_sec = index / max(fps, 1.0)
        times.append(round(8 * 60.0 + file_sec * hall_seconds / 60.0, 4))
    cap.release()
    if len(frames) < 2:
        raise ValueError("в файле слишком мало кадров")
    return frames, times, fps


def _fit(frame: np.ndarray) -> np.ndarray:
    return cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def _zone(path: Path, zone_id: str, hall_seconds: float, heat_mode: str, thermal_path: Path | None, night: bool, world_x0: float) -> ZoneClip:
    frames, times, _fps = _read_sampled(path, hall_seconds)
    if thermal_path is not None and heat_mode == "sensor":
        thermal_frames, _, _ = _read_sampled(thermal_path, hall_seconds)
        thermal = []
        for index in range(len(frames)):
            source = thermal_frames[min(index, len(thermal_frames) - 1)]
            thermal.append(gray_to_thermal(source))
        thermal_arr = np.stack(thermal)
    else:
        thermal_arr = np.full((len(frames), THERMAL_H, THERMAL_W), 24.0, dtype=np.float32)
    return ZoneClip(
        zone_id=zone_id,
        detect_frames=frames,
        show_frames=[frame.copy() for frame in frames],
        thermal=thermal_arr,
        times=times,
        nights=[night for _ in times],
        feeder_on=[False for _ in times],
        pan_px=OFF_PAN.copy(),
        world_x0=world_x0,
        heat_mode=heat_mode,
    )


def clip_from_files(
    zone1: Path,
    zone2: Path | None,
    thermal: Path | None,
    hall_seconds: float,
    teaching: bool,
    night: bool,
    planted: int,
    age_days: int,
) -> DemoClip:
    heat_mode = "teaching" if teaching else ("sensor" if thermal is not None else "none")
    zones = [_zone(zone1, "1", hall_seconds, heat_mode, thermal, night, 0.0)]
    if zone2 is not None:
        zones.append(_zone(zone2, "2", hall_seconds, heat_mode, thermal, night, WORLD_W))
    if teaching:
        note = "Учебный теплоканал подставлен явно. Это не запись тепловизора."
    elif thermal is not None:
        note = "Тепло читается из загруженной записи по яркости кадра."
    else:
        note = "В файле нет теплоканала, точки падежа не открываются."
    detector = ""
    from app.pipeline import WEIGHTS

    if not WEIGHTS.exists():
        detector = "Рамки по контрасту. Настоящие рамки птицы появятся после файла weights/birds.pt."
    return DemoClip(
        zones=zones,
        planted=planted,
        age_days=age_days,
        yesterday_still=None,
        section="свой ролик",
        heat_note=note,
        detector_note=detector,
        accelerated=hall_seconds != 1,
        playback="frames",
    )
