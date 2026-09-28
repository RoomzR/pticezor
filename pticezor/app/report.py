"""Лист сводки на этом компьютере. Наружу ничего не уходит."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1240, 1754
MARGIN = 56
INK = (28, 36, 33)
GREEN = (30, 58, 52)
SEEN = (90, 122, 110)
RUST = (142, 59, 47)
CAMERA = (60, 110, 143)
PAPER = (247, 244, 238)
LINE = (221, 214, 200)
MUTED = (94, 103, 95)
WHITE = (255, 252, 247)

_REGULAR = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_BOLD = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def build_report(payload: dict, kind: str) -> bytes:
    image = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    title = _font(40, bold=True)
    body = _font(16)
    small = _font(13)
    head = _font(18, bold=True)
    y = MARGIN
    name = "Лист обхода" if kind == "walk" else "Лист сводки"
    draw.text((MARGIN, y), "Птицезор", font=title, fill=GREEN)
    y += 52
    draw.line((MARGIN, y, W - MARGIN, y), fill=LINE, width=1)
    y += 18
    draw.text((MARGIN, y), name, font=head, fill=INK)
    y += 28
    mode = "Демо" if payload.get("mode") == "demo" else "Камеры"
    clock = payload.get("clock") or "—"
    hall = payload.get("hall") or {}
    place = hall.get("place") or "птичник"
    size = ""
    if hall.get("width_m") and hall.get("length_m"):
        size = f"{_comma(hall['width_m'])} × {_comma(hall['length_m'])} м"
    drawing = f", чертёж {hall['drawing']}" if hall.get("drawing") else ""
    draw.text((MARGIN, y), f"{mode}. Время {clock}. {place}. {size}{drawing}", font=small, fill=MUTED)
    y += 36
    if kind == "walk":
        y = _zones(draw, payload, y, body, small, head)
        y = _points(draw, payload, y, body, small, head)
    else:
        y = _numbers(draw, payload, y, body, small, head)
        y = _charts(draw, payload, y, small)
        y = _points(draw, payload, y, body, small, head)
    foot = "Лист этого обхода. Файл остаётся на компьютере." if kind == "walk" else "Сводка этого разбора. Файл остаётся на компьютере."
    draw.text((MARGIN, H - 48), foot, font=small, fill=MUTED)
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def _numbers(draw, payload, y, body, small, head) -> int:
    draw.text((MARGIN, y), "Цифры", font=head, fill=GREEN)
    y += 32
    weight = payload.get("weight") or {}
    activity = payload.get("activity") or {}
    rows = [
        ("Посажено по журналу", _fmt(payload.get("planted"))),
        ("Видно в зонах камер", _fmt(payload.get("visible"))),
        ("Расхождение", _fmt(payload.get("gap"))),
        ("Подтверждено, падаль", _fmt(payload.get("deaths_confirmed"))),
        ("Ждёт проверки", _fmt(payload.get("deaths_pending"))),
    ]
    if weight.get("hidden") or weight.get("median") is None:
        rows.append(("Вес", "не показываем" if payload.get("age_days", 0) < 5 else "нет медианы"))
    else:
        rows.append(("Медиана камеры, г", _fmt(weight.get("median"))))
        rows.append(("Норма кросса, г", _fmt(weight.get("norm"))))
        if weight.get("delta_pct") is not None:
            sign = "+" if weight["delta_pct"] > 0 else ""
            rows.append(("К норме", f"{sign}{weight['delta_pct']}%"))
    still = activity.get("still")
    if still is not None:
        rows.append(("Неподвижные", f"{round(still * 100)}%"))
    if activity.get("text"):
        rows.append(("Активность", str(activity["text"])))
    return _grid(draw, y, rows, body, small, pairs=True)


def _zones(draw, payload, y, body, small, head) -> int:
    draw.text((MARGIN, y), "Зоны", font=head, fill=GREEN)
    y += 32
    rows = [("Зона", "Пролёт", "Ждёт", "Падаль", "Тепло")]
    for item in payload.get("zone_report") or []:
        rows.append((
            str(item["id"]),
            item.get("bay") or "—",
            str(item["pending"]),
            str(item["dead"]),
            "сбой" if item.get("fault") else "—",
        ))
    if len(rows) == 1:
        rows.append(("—", "—", "0", "0", "—"))
    return _grid(draw, y, rows, body, small, header=True)


def _points(draw, payload, y, body, small, head) -> int:
    if y > H - 280:
        return y
    draw.text((MARGIN, y), "Точки", font=head, fill=GREEN)
    y += 32
    rows = [("Время", "Клетка", "Зона", "Статус")]
    points = payload.get("points") or []
    shown = points[:8]
    for point in shown:
        status = {"dead": "подтверждено", "alive": "живая", "pending": "ждёт"}.get(point.get("status"), point.get("status") or "")
        rows.append((str(point.get("t_label") or ""), str(point.get("cell") or ""), str(point.get("zone") or ""), status))
    if not shown:
        rows.append(("—", "—", "—", "точек нет"))
    y = _grid(draw, y, rows, body, small, header=True)
    if len(points) > len(shown):
        draw.text((MARGIN, y + 8), f"На экране ещё {len(points) - len(shown)}.", font=small, fill=MUTED)
        y += 28
    return y


def _charts(draw, payload, y, small) -> int:
    if y > H - 520:
        return y
    box_w = (W - MARGIN * 2 - 16) // 2
    box_h = 210
    weight = payload.get("weight") or {}
    heads = [
        {"label": "посажено", "value": payload.get("planted") or 0, "fill": GREEN},
        {"label": "видно", "value": payload.get("visible") or 0, "fill": SEEN},
    ]
    _chart(draw, (MARGIN, y, MARGIN + box_w, y + box_h), "Поголовье", heads, small)
    if not weight.get("hidden") and weight.get("median") is not None:
        bars = [
            {"label": "норма", "value": weight.get("norm") or 0, "fill": GREEN},
            {"label": "камера", "value": weight.get("median") or 0, "fill": CAMERA},
        ]
        if weight.get("control") is not None:
            bars.append({"label": "весы", "value": round(weight["control"]), "fill": SEEN})
        _chart(draw, (MARGIN + box_w + 16, y, W - MARGIN, y + box_h), "Вес, г", bars, small)
    else:
        reason = "Моложе пяти суток." if (payload.get("age_days") or 0) < 5 else "Нет медианы."
        _empty_chart(draw, (MARGIN + box_w + 16, y, W - MARGIN, y + box_h), "Вес, г", reason, small)
    y += box_h + 16
    hours = payload.get("hours") or []
    if len(hours) >= 2:
        still_bars = [
            {"label": str(row["hour"]), "value": round(row["fraction"] * 100), "fill": GREEN}
            for row in hours[-8:]
        ]
        caption = "Неподвижные, %"
    else:
        still = (payload.get("activity") or {}).get("still")
        still_bars = [{"label": "этот разбор", "value": 0 if still is None else round(still * 100), "fill": GREEN}]
        caption = "Неподвижные, %"
    _chart(draw, (MARGIN, y, MARGIN + box_w, y + box_h), caption, still_bars, small)
    point_bars = []
    for item in payload.get("zone_report") or []:
        point_bars.append({
            "label": str(item["id"]),
            "stack": [
                {"value": item["pending"], "fill": RUST},
                {"value": item["dead"], "fill": GREEN},
            ],
            "fault": item.get("fault"),
        })
    if not point_bars:
        point_bars = [{"label": "—", "value": 0, "fill": GREEN}]
    _chart(draw, (MARGIN + box_w + 16, y, W - MARGIN, y + box_h), "Точки по зонам", point_bars, small)
    return y + box_h + 28


def _chart(draw, box, title, rows, font) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=12, fill=PAPER, outline=LINE)
    draw.text((x0 + 16, y0 + 12), title, font=font, fill=MUTED)
    top = y0 + 44
    bottom = y1 - 36
    left = x0 + 16
    right = x1 - 16
    peak = 1
    for row in rows:
        total = row.get("value", 0)
        if row.get("stack"):
            total = sum(part["value"] for part in row["stack"])
        peak = max(peak, total)
    slot = max(1, (right - left) / max(len(rows), 1))
    bar_w = min(48, slot * 0.5)
    for index, row in enumerate(rows):
        cx = left + index * slot + slot / 2
        x = cx - bar_w / 2
        if row.get("stack"):
            acc = 0
            total = sum(part["value"] for part in row["stack"])
            for part in row["stack"]:
                h = (part["value"] / peak) * (bottom - top)
                y = bottom - ((acc + part["value"]) / peak) * (bottom - top)
                if part["value"]:
                    draw.rectangle((x, y, x + bar_w, y + max(h, 2)), fill=part["fill"])
                acc += part["value"]
            draw.text((cx, top + 2), str(total), font=font, fill=INK, anchor="mt")
            if row.get("fault"):
                draw.text((cx, y0 + 30), "сбой", font=font, fill=RUST, anchor="mt")
        else:
            h = max(2, (row["value"] / peak) * (bottom - top))
            draw.rectangle((x, bottom - h, x + bar_w, bottom), fill=row["fill"])
            draw.text((cx, bottom - h - 4), str(row["value"]), font=font, fill=INK, anchor="ms")
        draw.text((cx, bottom + 8), str(row["label"]), font=font, fill=MUTED, anchor="mt")
    draw.line((left, bottom, right, bottom), fill=LINE, width=1)


def _empty_chart(draw, box, title, reason, font) -> None:
    draw.rounded_rectangle(box, radius=12, fill=PAPER, outline=LINE)
    draw.text((box[0] + 16, box[1] + 12), title, font=font, fill=MUTED)
    draw.text((box[0] + 16, box[1] + 80), reason, font=font, fill=INK)


def _grid(draw, y, rows, body, small, header=False, pairs=False) -> int:
    row_h = 32
    width = W - MARGIN * 2
    cols = len(rows[0]) if rows else 2
    for index, row in enumerate(rows):
        if y + row_h > H - 70:
            break
        fill = (232, 239, 233) if header and index == 0 else PAPER if index % 2 else WHITE
        draw.rectangle((MARGIN, y, MARGIN + width, y + row_h), fill=fill)
        if pairs:
            label, value = row
            draw.text((MARGIN + 10, y + 7), str(label), font=body, fill=MUTED)
            draw.text((MARGIN + width - 220, y + 7), str(value), font=body, fill=INK)
        else:
            col_w = width / cols
            face = small if index == 0 and header else body
            color = GREEN if index == 0 and header else INK
            for col, value in enumerate(row):
                draw.text((MARGIN + 10 + col * col_w, y + 7), str(value), font=face, fill=color)
        y += row_h
    return y + 16


def _comma(value) -> str:
    return str(value).replace(".", ",")


def _fmt(value) -> str:
    if value is None:
        return "—"
    return str(value)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_BOLD if bold else _REGULAR):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
