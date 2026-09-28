"""Демо-ролик двух зон и теплоканал 160×120. Часы зала идут быстрее длины файла."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

WIDTH = 960
HEIGHT = 540
PX_PER_CM = 2.0
WORLD_W = WIDTH / PX_PER_CM
WORLD_H = HEIGHT / PX_PER_CM
THERMAL_W = 160
THERMAL_H = 120
START_MIN = 120.0  # 02:00
END_MIN = 145.0
STEP_MIN = 0.5
NIGHT_UNTIL = 140.0  # 02:20
FLOOR_C = 24.0
FLOOR_BASELINE_C = 24.0
BIRD_C = 38.0
PLANTED = 32
AGE_DAYS = 27
YESTERDAY_STILL = 0.20
SECTION = "демо-секция"


@dataclass
class Bird:
    x: float
    y: float
    w: float
    h: float
    temp: float
    vx: float = 0.0
    hidden: bool = False
    fault_temp: float | None = None


@dataclass
class ZoneScene:
    zone_id: str
    birds: list[Bird]
    gap_cm: tuple[float, float, float] | None
    pan_cm: tuple[float, float, float, float]
    fault_from: float | None = None
    fault_to: float | None = None
    world_x0: float = 0.0


@dataclass
class ZoneClip:
    zone_id: str
    detect_frames: list[np.ndarray]
    show_frames: list[np.ndarray]
    thermal: np.ndarray
    times: list[float]
    nights: list[bool]
    feeder_on: list[bool]
    pan_px: np.ndarray
    px_per_cm: float = PX_PER_CM
    world_x0: float = 0.0
    width_cm: float = WORLD_W
    height_cm: float = WORLD_H
    heat_mode: str = "sensor"


@dataclass
class DemoClip:
    zones: list[ZoneClip] = field(default_factory=list)
    planted: int = PLANTED
    age_days: int = AGE_DAYS
    yesterday_still: float | None = YESTERDAY_STILL
    section: str = SECTION
    floor_baseline_c: float = FLOOR_BASELINE_C
    heat_note: str = ""
    detector_note: str = ""
    accelerated: bool = True
    playback: str = "frames"


def hall_times() -> list[float]:
    times = []
    t = START_MIN
    while t <= END_MIN + 1e-9:
        times.append(round(t, 4))
        t += STEP_MIN
    return times


def _litter(rng: np.random.Generator) -> np.ndarray:
    noise = rng.integers(-6, 7, size=(HEIGHT, WIDTH, 1), dtype=np.int16)
    base = np.array([196, 204, 214], dtype=np.int16)
    image = np.clip(base + noise, 0, 255).astype(np.uint8)
    return image


def _ellipse(image: np.ndarray, bird: Bird, color: tuple[int, int, int]) -> None:
    cx = int(round(bird.x * PX_PER_CM))
    cy = int(round(bird.y * PX_PER_CM))
    ax = max(2, int(round(bird.w * PX_PER_CM / 2)))
    ay = max(2, int(round(bird.h * PX_PER_CM / 2)))
    cv2.ellipse(image, (cx, cy), (ax, ay), 0, 0, 360, color, -1)


def _thermal_paint(birds: list[Bird], gap: tuple[float, float, float] | None, fault: bool) -> np.ndarray:
    thermal = np.full((THERMAL_H, THERMAL_W), 12.0 if fault else FLOOR_C, dtype=np.float32)

    def to_px(x_cm: float, y_cm: float) -> tuple[int, int]:
        tx = int(round(x_cm / WORLD_W * (THERMAL_W - 1)))
        ty = int(round(y_cm / WORLD_H * (THERMAL_H - 1)))
        return tx, ty

    for bird in birds:
        temp = bird.temp
        if fault and bird.fault_temp is not None:
            temp = bird.fault_temp
        elif fault:
            temp = 20.0
        cx, cy = to_px(bird.x, bird.y)
        ax = max(2, int(round(bird.w / WORLD_W * THERMAL_W / 2)) + 1)
        ay = max(2, int(round(bird.h / WORLD_H * THERMAL_H / 2)) + 1)
        cv2.ellipse(thermal, (cx, cy), (ax, ay), 0, 0, 360, float(temp), -1)
    if gap is not None and not fault:
        gx, gy, gtemp = gap
        cx, cy = to_px(gx, gy)
        cv2.ellipse(thermal, (cx, cy), (4, 3), 0, 0, 360, float(gtemp), -1)
    return thermal


def _place(x: float, y: float, w: float, h: float, temp: float, vx: float = 0.0, hidden: bool = False, fault_temp: float | None = None) -> Bird:
    return Bird(x, y, w, h, temp, vx, hidden, fault_temp)


def zone_one() -> ZoneScene:
    birds = [
        _place(40, 230, 28, 12, 37.8),  # тёплая на боку, Г1
        _place(400, 180, 28, 12, 33.0),  # холодная на боку, В3
        _place(250, 180, 16, 12, BIRD_C),  # сидит
        _place(140, 48, 16, 11, BIRD_C),
        _place(146, 48, 16, 11, BIRD_C),
        _place(143, 54, 16, 11, BIRD_C),
        _place(325, 215, 16, 11, BIRD_C, hidden=True),
    ]
    xs = [36, 78, 250, 300, 340, 390, 70, 110]
    for index, x in enumerate(xs):
        birds.append(_place(x, 120, 16, 11, BIRD_C, vx=0.9 + index * 0.02))
    return ZoneScene("1", birds, (200, 30, 33.0), (300, 198, 50, 34), world_x0=0.0)


def zone_two() -> ZoneScene:
    birds = []
    for index in range(12):
        col = index % 4
        row = index // 4
        fault_temp = 20.0 if index < 6 else 40.0
        vx = 0.0 if index < 6 else 0.85
        birds.append(
            _place(
                50 + col * 100,
                50 + row * 70,
                16,
                11,
                BIRD_C,
                vx=vx,
                fault_temp=fault_temp,
            )
        )
    return ZoneScene("2", birds, None, (420, 20, 40, 28), fault_from=132.0, fault_to=136.0, world_x0=WORLD_W)


def _moved(bird: Bird, t_min: float) -> Bird:
    x = bird.x + bird.vx * (t_min - START_MIN)
    while x < 20 or x > WORLD_W - 20:
        if x < 20:
            x = 40 - x
        if x > WORLD_W - 20:
            x = 2 * (WORLD_W - 20) - x
    return Bird(x, bird.y, bird.w, bird.h, bird.temp, bird.vx, bird.hidden, bird.fault_temp)


def _pan_px(pan_cm: tuple[float, float, float, float]) -> np.ndarray:
    x, y, w, h = pan_cm
    pts = [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h),
    ]
    return np.array([(int(px * PX_PER_CM), int(py * PX_PER_CM)) for px, py in pts], dtype=np.int32)


def render_zone(scene: ZoneScene, rng: np.random.Generator) -> ZoneClip:
    times = hall_times()
    detect_frames: list[np.ndarray] = []
    show_frames: list[np.ndarray] = []
    thermals: list[np.ndarray] = []
    nights: list[bool] = []
    feeder: list[bool] = []
    litter = _litter(rng)
    for t_min in times:
        moved = [_moved(bird, t_min) for bird in scene.birds]
        fault = (
            scene.fault_from is not None
            and scene.fault_to is not None
            and scene.fault_from <= t_min <= scene.fault_to
        )
        detect = litter.copy()
        for bird in moved:
            if bird.hidden:
                continue
            _ellipse(detect, bird, (48, 52, 58))
        pan = _pan_px(scene.pan_cm)
        cv2.fillPoly(detect, [pan], (205, 198, 184))
        show = detect.copy()
        cv2.polylines(show, [pan], True, (90, 110, 140), 2)
        for y_cm in (90, 170, 250):
            y = int(y_cm * PX_PER_CM)
            cv2.line(show, (24, y), (WIDTH - 24, y), (170, 185, 200), 3)
        detect_frames.append(detect)
        show_frames.append(show)
        thermals.append(_thermal_paint(moved, scene.gap_cm, fault))
        nights.append(t_min < NIGHT_UNTIL)
        feeder.append(t_min < START_MIN + 4)
    return ZoneClip(
        zone_id=scene.zone_id,
        detect_frames=detect_frames,
        show_frames=show_frames,
        thermal=np.stack(thermals),
        times=times,
        nights=nights,
        feeder_on=feeder,
        pan_px=pan,
        world_x0=scene.world_x0,
    )


def build_demo() -> DemoClip:
    rng = np.random.default_rng(1)
    return DemoClip(zones=[render_zone(zone_one(), rng), render_zone(zone_two(), rng)])
