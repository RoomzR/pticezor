"""Рамки птицы: контуры на демо-ролике или YOLO, если рядом лежит файл весов. След — ByteTrack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.rules import in_any_mask


@dataclass
class TrackedBox:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    merged: bool
    edge: bool

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def w(self) -> float:
        return self.x2 - self.x1

    @property
    def h(self) -> float:
        return self.y2 - self.y1


def contour_boxes(frame_bgr: np.ndarray, mask_polys_px: list[np.ndarray]) -> np.ndarray:
    image = frame_bgr.copy()
    for poly in mask_polys_px:
        cv2.fillPoly(image, [poly], (205, 198, 184))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[list[float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 180 or area > 12000:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        boxes.append([float(x), float(y), float(x + w), float(y + h)])
    if not boxes:
        return np.zeros((0, 4), dtype=np.float32)
    return np.asarray(boxes, dtype=np.float32)


_yolo_model = None


def yolo_boxes(frame_bgr: np.ndarray, weights: Path) -> np.ndarray:
    global _yolo_model
    from ultralytics import YOLO

    if _yolo_model is None:
        _yolo_model = YOLO(str(weights))
    result = _yolo_model.predict(frame_bgr, verbose=False, conf=0.25)[0]
    if result.boxes is None or len(result.boxes) == 0:
        return np.zeros((0, 4), dtype=np.float32)
    return result.boxes.xyxy.cpu().numpy().astype(np.float32)


def _new_tracker():
    import warnings

    import supervision as sv

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            return sv.ByteTrack(
                minimum_consecutive_frames=1,
                lost_track_buffer=20,
                frame_rate=5,
            )
    except TypeError:
        return sv.ByteTrack()


def _track_one(tracker, boxes: np.ndarray) -> list[tuple[int, np.ndarray]]:
    import supervision as sv

    if len(boxes) == 0:
        detections = sv.Detections.empty()
    else:
        detections = sv.Detections(
            xyxy=boxes,
            confidence=np.ones(len(boxes), dtype=np.float32),
        )
    updated = tracker.update_with_detections(detections)
    rows: list[tuple[int, np.ndarray]] = []
    if updated.tracker_id is None:
        return rows
    for box, tid in zip(updated.xyxy, updated.tracker_id):
        rows.append((int(tid), box))
    return rows


def _decorate(rows: list[tuple[int, np.ndarray]], width: int, height: int) -> list[TrackedBox]:
    boxes = [box for _, box in rows]
    areas = [max(0.0, float(b[2] - b[0]) * float(b[3] - b[1])) for b in boxes]
    median_area = float(np.median(areas)) if areas else 1.0
    frame_rows: list[TrackedBox] = []
    for index, (tid, box) in enumerate(rows):
        x1, y1, x2, y2 = [float(v) for v in box]
        overlap = any(_iou(box, other) > 0.15 for other_index, other in enumerate(boxes) if other_index != index)
        edge = x1 < 8 or y1 < 8 or x2 > width - 8 or y2 > height - 8
        frame_rows.append(
            TrackedBox(
                track_id=tid,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                merged=overlap or areas[index] > median_area * 2.4,
                edge=edge,
            )
        )
    return frame_rows


class TrackerSession:
    def __init__(self, weights: Path | None):
        self.weights = weights if weights is not None and Path(weights).exists() else None
        self._tracker = _new_tracker()

    def step(self, frame: np.ndarray, mask_polys_px: list[np.ndarray]) -> list[TrackedBox]:
        height, width = frame.shape[:2]
        boxes = yolo_boxes(frame, self.weights) if self.weights else contour_boxes(frame, mask_polys_px)
        return _decorate(_track_one(self._tracker, boxes), width, height)


def track_video(
    frames_bgr: list[np.ndarray],
    mask_polys_px: list[np.ndarray],
    weights: Path | None = None,
) -> list[list[TrackedBox]]:
    session = TrackerSession(weights)
    return [session.step(frame, mask_polys_px) for frame in frames_bgr]


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def upsample_thermal(thermal: np.ndarray, width: int, height: int) -> np.ndarray:
    return cv2.resize(thermal, (width, height), interpolation=cv2.INTER_NEAREST)


def sample_center(thermal: np.ndarray, box: TrackedBox) -> float:
    cx = int(round(box.cx))
    cy = int(round(box.cy))
    y1 = max(0, cy - 1)
    y2 = min(thermal.shape[0], cy + 2)
    x1 = max(0, cx - 1)
    x2 = min(thermal.shape[1], cx + 2)
    patch = thermal[y1:y2, x1:x2]
    if patch.size == 0:
        return float(thermal[min(cy, thermal.shape[0] - 1), min(cx, thermal.shape[1] - 1)])
    return float(np.median(patch))


def sample_floor(thermal: np.ndarray, boxes: list[TrackedBox]) -> float:
    mask = np.ones(thermal.shape[:2], dtype=bool)
    for box in boxes:
        x1 = max(0, int(box.x1))
        y1 = max(0, int(box.y1))
        x2 = min(thermal.shape[1], int(box.x2))
        y2 = min(thermal.shape[0], int(box.y2))
        mask[y1:y2, x1:x2] = False
    values = thermal[mask]
    if values.size == 0:
        return float(np.median(thermal))
    return float(np.median(values))


def find_gap_spots(
    thermal: np.ndarray,
    boxes: list[TrackedBox],
    temps: list[float],
    mask_polys_px: list[np.ndarray],
    floor_temp: float,
) -> list[tuple[float, float, float]]:
    if not temps:
        return []
    median = float(np.median(temps))
    # Пол и так холоднее птицы. Пятно между головами — тело: холоднее соседей, но теплее пола.
    high = median - 4.0
    low = floor_temp + 3.0
    if high <= low:
        return []
    cold = ((thermal <= high) & (thermal >= low)).astype(np.uint8)
    for box in boxes:
        x1 = max(0, int(box.x1) - 24)
        y1 = max(0, int(box.y1) - 24)
        x2 = min(cold.shape[1], int(box.x2) + 24)
        y2 = min(cold.shape[0], int(box.y2) + 24)
        cold[y1:y2, x1:x2] = 0
    for poly in mask_polys_px:
        cv2.fillPoly(cold, [poly], 0)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(cold)
    spots: list[tuple[float, float, float]] = []
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area < 180 or area > 3000:
            continue
        cx, cy = centroids[index]
        blob = thermal[labels == index]
        spots.append((float(cx), float(cy), float(np.median(blob))))
    return spots


def box_in_mask(box: TrackedBox, masks_px: list[list[tuple[float, float]]]) -> bool:
    return in_any_mask(box.cx, box.cy, masks_px)
