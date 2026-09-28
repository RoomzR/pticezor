"""Камеры встают на зоны плана. Лишнее устройство становится тепловизором."""

from __future__ import annotations


def assign_cameras(zone_ids: list[str], cameras: list[dict]) -> list[dict]:
    rows = [{"id": zone_id, "rgb": None, "thermal": None} for zone_id in zone_ids]
    indexes = []
    for camera in cameras:
        index = camera.get("index")
        if index is None or index in indexes:
            continue
        indexes.append(int(index))
    for row, index in zip(rows, indexes):
        row["rgb"] = index
    slot = 0
    for index in indexes[len(rows):]:
        for _ in range(len(rows)):
            row = rows[slot % len(rows)] if rows else None
            slot += 1
            if row is None or row["rgb"] is None or row["thermal"] is not None or row["rgb"] == index:
                continue
            row["thermal"] = index
            break
    return rows
