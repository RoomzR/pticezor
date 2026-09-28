"""План общего зала. Готовый чертёж цеха «Сож» и сборка плана из размеров."""

from __future__ import annotations

LENGTH_GAPS_M = (6.0, 0.5, *([6.0] * 15))
# Разрез 1-1: 6 000 между Б–Г и Г–Е раскрыты как 1 500 + 4 500 и 4 500 + 1 500.
WIDTH_GAPS_M = (4.5, 1.5, 4.5, 4.5, 1.5, 4.5)
WIDTH_GROUPED_M = (4.5, 6.0, 6.0, 4.5)
AXIS_X = tuple(str(n) for n in range(1, 19))
AXIS_Y = ("А", "Б", "В", "Г", "Д", "Е", "Ж")
# Два ряда по 2,7 м. Проход 1,2 м (600 + 600) сидит на оси Г.
NESTS_M = ({"y_m": 7.2, "h_m": 2.7}, {"y_m": 11.1, "h_m": 2.7})
# Ряды поения с плана расстановки: четыре с каждой стороны, не через гнёзда.
FEED_LINES_M = (0.7, 1.3, 2.9, 5.8, 15.2, 18.1, 19.7, 20.3)
MAX_ZONES = 6


def _stops(gaps: tuple[float, ...] | list[float]) -> list[float]:
    stops = [0.0]
    for gap in gaps:
        stops.append(round(stops[-1] + gap, 1))
    return stops


def _letters(count: int) -> list[str]:
    alphabet = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩ"
    return list(alphabet[:count])


def bays_of(x_m: list[float], vestibule_end: float, axes_x: list[str]) -> list[dict]:
    bays = []
    index = 0
    for i in range(len(x_m) - 1):
        gap = round(x_m[i + 1] - x_m[i], 1)
        if x_m[i] < vestibule_end - 0.05 or gap < 4:
            continue
        bays.append({
            "index": index,
            "x_m": x_m[i],
            "w_m": gap,
            "label": f"{axes_x[i]}–{axes_x[i + 1]}",
        })
        index += 1
    return bays


def place_zones(bays: list[dict], litter_m: float, count: int) -> list[dict]:
    count = max(1, min(MAX_ZONES, count))
    if not bays:
        return []
    if len(bays) >= count + 5:
        start = 5
    else:
        start = max(0, (len(bays) - count) // 2)
    chosen = bays[start:start + count]
    height = min(2.7, max(1.2, litter_m - 0.4))
    y_m = 0.9 if litter_m >= height + 0.9 else 0.2
    zones = []
    for number, bay in enumerate(chosen, start=1):
        zones.append({
            "id": str(number),
            "x_m": bay["x_m"],
            "y_m": y_m,
            "w_m": round(min(4.8, bay["w_m"] - 0.2), 1),
            "h_m": round(height, 1),
            "bay": bay["label"],
        })
    return zones


def _lines(y_m: list[float], nests: list[dict] | None) -> list[float]:
    rows = nests or []
    lines = []
    for start, end in zip(y_m, y_m[1:]):
        if end - start < 2:
            continue
        mid = round((start + end) / 2, 1)
        if any(item["y_m"] <= mid <= item["y_m"] + item["h_m"] for item in rows):
            continue
        lines.append(mid)
    return lines


def build_plan(
    length_gaps: tuple[float, ...] | list[float],
    width_gaps: tuple[float, ...] | list[float],
    *,
    vestibule_end: float,
    nest_h: float | None = None,
    nests: list[dict] | None = None,
    zone_count: int = 2,
    title: str = "Общий зал",
    place: str = "птичник",
    drawing: str = "",
    note: str = "",
    vestibule_label: str = "тамбур",
    nest_label: str = "ряд по центру",
    axes_y: list[str] | None = None,
    lines: list[float] | None = None,
) -> dict:
    x_m = _stops(length_gaps)
    y_m = _stops(width_gaps)
    axes_x = [str(number) for number in range(1, len(x_m) + 1)]
    axes = axes_y if axes_y and len(axes_y) == len(y_m) else _letters(len(y_m))
    if nests:
        nest_rows = [{"y_m": round(float(item["y_m"]), 2), "h_m": round(float(item["h_m"]), 2)} for item in nests]
    elif nest_h and nest_h > 0:
        center = y_m[-1] / 2
        nest_rows = [{"y_m": round(center - nest_h / 2, 2), "h_m": nest_h}]
    else:
        nest_rows = []
    bays = bays_of(x_m, vestibule_end, axes_x)
    litter = width_gaps[0] if width_gaps else y_m[-1]
    return {
        "title": title,
        "place": place,
        "drawing": drawing,
        "length_m": x_m[-1],
        "width_m": y_m[-1],
        "axes_x": axes_x,
        "axes_y": list(axes),
        "x_m": x_m,
        "y_m": y_m,
        "vestibule_m": [0.0, round(vestibule_end, 1)],
        "vestibule_label": vestibule_label,
        "nest": nest_rows[0] if len(nest_rows) == 1 else None,
        "nests": nest_rows,
        "nest_label": nest_label,
        "lines_y_m": lines if lines is not None else _lines(y_m, nest_rows),
        "bays": bays,
        "zones": place_zones(bays, litter, zone_count),
        "note": note,
    }


def hall_plan() -> dict:
    return build_plan(
        LENGTH_GAPS_M,
        WIDTH_GAPS_M,
        vestibule_end=6.5,
        nests=[dict(item) for item in NESTS_M],
        zone_count=2,
        title="Общий зал",
        place="цех «Сож», РУП «Белоруснефть-Особино»",
        drawing="38.23-1+6",
        vestibule_label="тамбур 1–12",
        nest_label="гнёзда",
        axes_y=list(AXIS_Y),
        lines=list(FEED_LINES_M),
        note=(
            "Птичник родительского стада. Тамбур в осях 1–3, помещения 1–12. "
            "Ширина 21 м: 4,5 + 1,5 + 4,5 + 4,5 + 1,5 + 4,5. На плане пролёты Б–Г и Г–Е сведены в 6 м. "
            "Два ряда гнёзд по 2,7 м, между ними проход 1,2 м по оси Г. "
            "Линии кормления идут по боковым пролётам. Зоны камер — участки пола, клетки А1–Г3 считаются внутри кадра."
        ),
    )


def plan_from_totals(length_m: float, width_m: float, vestibule_m: float, zone_count: int) -> dict:
    if not (20 <= length_m <= 200 and 8 <= width_m <= 40):
        raise ValueError("Размеры зала вне обычного птичника.")
    if vestibule_m < 0 or vestibule_m >= length_m:
        raise ValueError("Тамбур должен быть короче зала.")
    if not 1 <= zone_count <= MAX_ZONES:
        raise ValueError("Зон от 1 до 6.")
    length_gaps: list[float] = []
    if vestibule_m > 0:
        length_gaps.append(round(vestibule_m, 1))
    rest = round(length_m - vestibule_m, 1)
    while rest > 6.5:
        length_gaps.append(6.0)
        rest = round(rest - 6.0, 1)
    if rest >= 0.4:
        length_gaps.append(rest)
    side = 4.5 if width_m >= 12 else round(width_m, 1)
    width_gaps = [side] if abs(side - width_m) < 0.2 else [side, round(width_m - side, 1)]
    return build_plan(
        length_gaps,
        width_gaps,
        vestibule_end=round(vestibule_m, 1),
        zone_count=zone_count,
        drawing="схема",
        note="План по введённым размерам. Зоны камер — участки пола, клетки А1–Г3 считаются внутри кадра.",
    )


def toggle_bay(plan: dict, bay_index: int) -> tuple[dict, str]:
    bay = next((item for item in plan.get("bays") or [] if item["index"] == bay_index), None)
    if bay is None:
        return plan, "Такого пролёта нет."
    zones = [dict(item) for item in plan.get("zones") or []]
    kept = [item for item in zones if abs(item["x_m"] - bay["x_m"]) >= 0.2]
    if len(kept) != len(zones):
        zones = kept
        message = ""
    elif len(zones) >= MAX_ZONES:
        return plan, "На этом компьютере не больше шести зон."
    else:
        sample = zones[0] if zones else {"y_m": 0.9, "h_m": 2.7}
        zones.append({
            "id": "0",
            "x_m": bay["x_m"],
            "y_m": sample["y_m"],
            "w_m": round(min(4.8, bay["w_m"] - 0.2), 1),
            "h_m": sample["h_m"],
            "bay": bay["label"],
        })
        message = ""
    zones.sort(key=lambda item: item["x_m"])
    for number, item in enumerate(zones, start=1):
        item["id"] = str(number)
    plan = {**plan, "zones": zones}
    return plan, message
