"""Разбор схемы птичника на этом компьютере. Файл наружу не уходит."""

from __future__ import annotations

import re
from pathlib import Path

from app.hall import LENGTH_GAPS_M, WIDTH_GAPS_M, WIDTH_GROUPED_M, build_plan, hall_plan

BLANK = {"length_m": None, "width_m": None, "vestibule_m": None, "zones": None}
_LOOKALIKE = str.maketrans({
    "O": "0", "o": "0", "О": "0", "о": "0", "Q": "0", "q": "0",
    "I": "1", "l": "1", "S": "5", "s": "5", "B": "8", "З": "3", "з": "3",
})


def assemble_chain(
    hits: list[tuple[float, int]],
    overall: int | None = None,
    *,
    least: int = 2,
    drop_strays: bool = False,
) -> list[int] | None:
    """Цепочка из прочитанных чисел. Недостающий кусок берётся только если на листе есть общий размер."""
    usable = [(pos, value) for pos, value in hits if 400 <= int(value) <= 15000 and int(value) % 50 == 0]
    if not usable:
        return None
    span = max(pos for pos, _ in usable) - min(pos for pos, _ in usable)
    tolerance = max(span * 0.018, 1e-6)
    prefer = None
    if drop_strays:
        counted = [value for _, value in usable if value % 100 == 0]
        if not counted:
            return None
        prefer = max(set(counted), key=counted.count)
        usable = [(pos, value) for pos, value in usable if value == prefer or 400 <= value <= 2500]
    deduped = _dedupe(usable, tolerance, prefer)
    if not deduped:
        return None
    if drop_strays:
        mode = max(set(value for _, value in deduped), key=[value for _, value in deduped].count)
        modal = [(pos, value) for pos, value in deduped if value == mode]
        small = [(pos, value) for pos, value in deduped if value != mode]
        chain = [value for _, value in modal]
        if overall and sum(chain) != overall:
            missing = overall - sum(chain)
            piece = next((value for _, value in small if value == missing), None)
            if piece is None and 400 <= missing <= 2500 and missing % 50 == 0:
                piece = missing
            if piece is not None:
                chain.insert(_widest_slot(modal), piece)
    else:
        chain = [value for _, value in deduped]
        if overall and sum(chain) != overall:
            missing = overall - sum(chain)
            if 400 <= missing <= 2500 and missing % 50 == 0:
                chain.insert(_widest_slot(deduped), missing)
    if len(chain) < least:
        return None
    meters = sum(chain) / 1000
    if least >= 6 and not 30 <= meters <= 160:
        return None
    if least < 6 and not 8 <= meters <= 40:
        return None
    if overall and sum(chain) != overall:
        return None
    return chain


def _dedupe(hits: list[tuple[float, int]], tolerance: float, prefer: int | None) -> list[tuple[float, int]]:
    groups: list[list[tuple[float, int]]] = []
    for pos, value in sorted(hits, key=lambda item: item[0]):
        if groups and pos - groups[-1][-1][0] <= tolerance:
            groups[-1].append((pos, value))
        else:
            groups.append([(pos, value)])
    result = []
    for group in groups:
        values = [value for _, value in group]
        chosen = prefer if prefer in values else max(set(values), key=values.count)
        result.append((sum(pos for pos, _ in group) / len(group), chosen))
    return result


def _widest_slot(hits: list[tuple[float, int]]) -> int:
    if len(hits) < 2:
        return 1 if hits else 0
    gaps = [hits[index + 1][0] - hits[index][0] for index in range(len(hits) - 1)]
    return gaps.index(max(gaps)) + 1


def parse_sheet_text(text: str, drawing: str = "") -> dict:
    values, area = _millimeters(text)
    pair = _choose_pair(values, area)
    if pair is None:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK)}
    length, width = pair
    length_gaps = [round(values[i] / 1000, 1) for i in range(length[0], length[1] + 1)]
    width_gaps = [round(values[i] / 1000, 1) for i in range(width[0], width[1] + 1)]
    vestibule = _vestibule(length_gaps)
    nest_h = _nest(values, length, width)
    letters = _axis_letters(text)
    axes_y = letters if len(letters) == len(width_gaps) + 1 else None
    place = "птичник"
    if "Особино" in text or "Особино".lower() in text.lower():
        place = "цех «Сож», РУП «Белоруснефть-Особино»" if "Сож" in text else "РУП «Белоруснефть-Особино»"
    note = "Зоны камер — участки пола, клетки А1–Г3 считаются внутри кадра."
    if "родительск" in text.lower():
        note = "Птичник родительского стада. " + note
    plan = build_plan(
        length_gaps,
        width_gaps,
        vestibule_end=vestibule,
        nest_h=nest_h,
        zone_count=2,
        place=place,
        drawing=drawing,
        axes_y=axes_y,
        note=note,
    )
    return {"plan": plan, "needs_confirm": False, "fields": dict(BLANK)}


def read_plan(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return _read_bitmap(path)
    return {"plan": None, "needs_confirm": True, "fields": dict(BLANK), "png": b""}


def _parse_page(page: dict, drawing: str) -> dict:
    text = page.get("text") or ""
    parsed = parse_sheet_text(text, drawing) if text.strip() else {"plan": None}
    if parsed.get("plan") is not None:
        return parsed
    image = page.get("image")
    if image is None:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK)}
    length, width = _chains_from_image(image)
    if not length or not width:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK)}
    plan = _plan_from_chains(length, width, drawing)
    if plan is None:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK)}
    return {"plan": plan, "needs_confirm": False, "fields": dict(BLANK)}


def _plan_from_chains(length_mm: list[int], width_mm: list[int], drawing: str) -> dict | None:
    length_m = [round(value / 1000, 1) for value in length_mm]
    width_m = [round(value / 1000, 1) for value in width_mm]
    known = (
        [round(value, 1) for value in WIDTH_GAPS_M],
        [round(value, 1) for value in WIDTH_GROUPED_M],
    )
    if length_m == [round(value, 1) for value in LENGTH_GAPS_M] and width_m in known:
        plan = hall_plan()
        if drawing:
            plan["drawing"] = drawing
        return plan
    try:
        return build_plan(
            length_m,
            width_m,
            vestibule_end=_vestibule(length_m),
            nest_h=_nest(length_mm, (0, len(length_mm) - 1), (len(length_mm), len(length_mm) + len(width_mm) - 1)),
            zone_count=2,
            drawing=drawing,
            note="Зоны камер — участки пола, клетки А1–Г3 считаются внутри кадра.",
        )
    except (ValueError, IndexError, ZeroDivisionError):
        return None


def _chains_from_image(image) -> tuple[list[int] | None, list[int] | None]:
    cropped = _crop_ink(image)
    if cropped is None:
        return None, None
    width, height = cropped.size
    if width < 200 or height < 120 or width / height < 1.25:
        return None, None
    length = _length_chain(cropped)
    if not length:
        return None, None
    return length, _width_chain(cropped)


def _length_chain(image) -> list[int] | None:
    best = None
    for top, bottom in ((0.50, 0.92),):
        hits = _band_hits(image, top, bottom, tiles=8)
        chain = _length_from_hits(hits)
        if chain and (best is None or sum(chain) > sum(best)):
            best = chain
    return best


def _length_from_hits(hits: list[tuple[float, int]]) -> list[int] | None:
    bays = [(pos, value) for pos, value in hits if 400 <= value <= 15000]
    if not bays:
        return None
    counted = [value for _, value in bays if value % 100 == 0]
    if not counted:
        return None
    mode = max(set(counted), key=counted.count)
    span = max(pos for pos, _ in bays) - min(pos for pos, _ in bays)
    modal = _dedupe([(pos, value) for pos, value in bays if value == mode], max(span * 0.018, 1e-6), mode)
    if len(modal) < 6:
        return None
    base = len(modal) * mode
    overalls = []
    for _pos, value in hits:
        cleaned = _clean_overall(value)
        if cleaned and 30000 <= cleaned <= 160000:
            overalls.append(cleaned)
    close = [value for value in overalls if 0 <= value - base <= 2500]
    overall = max(close) if close else None
    return assemble_chain(bays, overall, least=6, drop_strays=True)


def _width_chain(image) -> list[int] | None:
    width, height = image.size
    windows = ((0.10, 0.18), (0.08, 0.16), (0.12, 0.20), (0.05, 0.13))
    best = None
    for left, right in windows:
        strip = image.crop((int(width * left), int(height * 0.12), int(width * right), int(height * 0.76)))
        if strip.width < 8 or strip.height < 8:
            continue
        rows = _recognize(_enlarge(strip, 3).rotate(-90, expand=True))
        hits = []
        for pos, _y, text in rows:
            numbers = [value for value in _values(text) if 400 <= value <= 15000 and value % 500 == 0]
            if numbers:
                hits.append((pos, numbers[0]))
        chain = assemble_chain(hits, None, least=2, drop_strays=False)
        if chain and (best is None or (len(chain), sum(chain)) > (len(best), sum(best))):
            best = chain
    return best


def _clean_overall(value: int) -> int | None:
    if value % 100 == 0:
        return value
    nearest = int(round(value / 100) * 100)
    if abs(nearest - value) <= 20:
        return nearest
    return None


def _band_hits(image, top: float, bottom: float, tiles: int) -> list[tuple[float, int]]:
    width, height = image.size
    y0, y1 = int(height * top), int(height * bottom)
    found = []
    for index in range(tiles):
        x0 = int(index * width / tiles)
        x1 = int(min(width, (index + 1) * width / tiles + width * 0.03))
        tile = _enlarge(image.crop((x0, y0, max(x0 + 1, x1), max(y0 + 1, y1))), 2)
        for center, _y, text in _recognize(tile):
            gx = x0 + center * (x1 - x0)
            for value in _values(text):
                found.append((gx, value))
    return _merge_split_overalls(found)


def _merge_split_overalls(hits: list[tuple[float, int]]) -> list[tuple[float, int]]:
    if not hits:
        return []
    ordered = sorted(hits, key=lambda item: item[0])
    span = max(pos for pos, _ in ordered) - min(pos for pos, _ in ordered) or 1
    merged = []
    index = 0
    while index < len(ordered):
        pos, value = ordered[index]
        if index + 1 < len(ordered):
            nxt, other = ordered[index + 1]
            joined = int(f"{value}{other}")
            if value < 1000 and other < 1000 and nxt - pos <= span * 0.04 and 20000 <= joined <= 200000:
                merged.append((pos, joined))
                index += 2
                continue
        merged.append((pos, value))
        index += 1
    return merged


def _overall_near(hits: list[tuple[float, int]], *, low: int, high: int) -> int | None:
    found = [value for _pos, value in hits if low <= value <= high and value % 100 == 0]
    if not found:
        return None
    return max(set(found), key=found.count)


def _values(text: str) -> list[int]:
    cleaned = re.sub(r"(?<=\d)\s+(?=\d)", "", text.translate(_LOOKALIKE))
    return [int(chunk) for chunk in re.findall(r"\d{2,6}", cleaned)]


def _crop_ink(image):
    gray = image.convert("L")
    mask = gray.point(lambda pixel: 255 if pixel < 245 else 0)
    box = mask.getbbox()
    if box is None:
        return None
    return image.crop(box)


def _enlarge(image, factor: int):
    from PIL import ImageOps

    resized = image.resize((max(1, image.width * factor), max(1, image.height * factor)))
    return ImageOps.autocontrast(resized)


def _recognize(image) -> list[tuple[float, float, str]]:
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        return []
    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    try:
        image.save(target, format="PNG")
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(1)
        request.setUsesLanguageCorrection_(False)
        try:
            request.setRecognitionLanguages_(["ru-RU", "en-US"])
        except Exception:
            pass
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(target)), None)
        success, _error = handler.performRequests_error_([request], None)
        if not success:
            return []
        rows = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue
            box = observation.boundingBox()
            rows.append((box.origin.x + box.size.width / 2, box.origin.y, str(candidates[0].string())))
        return rows
    finally:
        target.unlink(missing_ok=True)


def _drawing_name(stem: str, text: str) -> str:
    blob = f"{stem}\n{text}"
    if re.search(r"38[\.\-_]?23[\.\-_]?1", blob):
        return "38.23-1+6"
    return stem[:40]


def _read_pdf(path: Path) -> dict:
    try:
        import Quartz
        from Foundation import NSURL
    except ImportError:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK), "png": b""}
    document = Quartz.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(str(path)))
    if document is None:
        return {"plan": None, "needs_confirm": True, "fields": dict(BLANK), "png": b""}
    drawing = _drawing_name(path.stem, "")
    sheet = b""
    texts = []
    count = min(int(document.pageCount()), 12)
    for index in range(count):
        page = document.pageAtIndex_(index)
        text = page.string() or ""
        texts.append(text)
        png = _render_pdf_page(document, index)
        image = _open_png(png)
        parsed = _parse_page({"text": text, "image": image, "png": png}, drawing)
        if png:
            sheet = png
        if parsed.get("plan") is not None:
            parsed["png"] = png
            return parsed
    chosen = parse_sheet_text("\n".join(texts), drawing)
    chosen["png"] = sheet
    return chosen


def _read_bitmap(path: Path) -> dict:
    image = _open_png(path.read_bytes())
    drawing = _drawing_name(path.stem, "")
    parsed = _parse_page({"text": "", "image": image}, drawing)
    if parsed.get("plan") is None:
        parsed = parse_sheet_text(_ocr(path), drawing)
    parsed["png"] = path.read_bytes()
    return parsed


def _open_png(payload: bytes):
    if not payload:
        return None
    import io

    from PIL import Image

    return Image.open(io.BytesIO(payload)).convert("RGB")


def _millimeters(text: str) -> tuple[list[int], float | None]:
    area = None
    match = re.search(r"площад[^\d]{0,40}(\d{3,5}[,.]\d+)", text, flags=re.IGNORECASE)
    cleaned = text
    if match:
        area = float(match.group(1).replace(",", "."))
        cleaned = cleaned.replace(match.group(1), " ")
    values = []
    for found in re.finditer(r"(?<!\d)(\d{3,5})(?!\d)", cleaned):
        number = int(found.group(1))
        if 400 <= number <= 15000:
            values.append(number)
    return values, area


def _choose_pair(values: list[int], area: float | None):
    lengths = []
    widths = []
    for start in range(len(values)):
        total = 0
        for end in range(start, len(values)):
            total += values[end]
            count = end - start + 1
            meters = total / 1000
            if meters > 160:
                break
            if count >= 6 and 30 <= meters <= 160 and _continuous(values[start:end + 1]):
                lengths.append((start, end, meters))
            if 2 <= count <= 8 and 8 <= meters <= 40:
                widths.append((start, end, meters))
    pairs = []
    for length in lengths:
        for width in widths:
            if not (length[1] < width[0] or width[1] < length[0]):
                continue
            product = length[2] * width[2]
            if area is not None and abs(product - area) / area > 0.08:
                continue
            pairs.append((length, width, product))
    if not pairs:
        return None
    if area is not None:
        pairs.sort(key=lambda item: (abs(item[2] - area), -(item[0][1] - item[0][0])))
    else:
        pairs.sort(key=lambda item: (-(item[0][1] - item[0][0]), _width_rank(item[1][2])))
    best = pairs[0]
    return best[0], best[1]


def _continuous(chunk: list[int]) -> bool:
    rounded = [round(number / 1000, 1) for number in chunk]
    mode = max(set(rounded), key=rounded.count)
    return rounded.count(mode) >= len(rounded) / 2


def _width_rank(meters: float) -> float:
    if 12 <= meters <= 24:
        return 0
    return min(abs(meters - 12), abs(meters - 24))


def _vestibule(gaps: list[float]) -> float:
    depth = 0.0
    for index, gap in enumerate(gaps[:3]):
        depth += gap
        if gap < 2:
            return round(depth, 1)
    return 0.0


def _nest(values: list[int], length, width) -> float | None:
    used = set(range(length[0], length[1] + 1)) | set(range(width[0], width[1] + 1))
    for index, number in enumerate(values):
        if index in used:
            continue
        if 1900 <= number <= 2300:
            return round(number / 1000, 1)
    return None


def _axis_letters(text: str) -> list[str]:
    found = []
    for match in re.finditer(r"(?:^|[^\w])([АБВГДЕЖ])(?=$|[^\w])", text, flags=re.MULTILINE):
        letter = match.group(1)
        if letter not in found:
            found.append(letter)
    return found


def _pages(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_pages(path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        text = _ocr(path)
        return [{"text": text, "png": path.read_bytes()}]
    return []


def _pdf_pages(path: Path) -> list[dict]:
    try:
        import Quartz
        from Foundation import NSURL
    except ImportError:
        return []
    document = Quartz.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(str(path)))
    if document is None:
        return []
    pages = []
    count = min(int(document.pageCount()), 8)
    texts = []
    for index in range(count):
        page = document.pageAtIndex_(index)
        texts.append(page.string() or "")
    need_ocr = sum(len(re.findall(r"\d{3,5}", text)) for text in texts) < 12
    for index in range(count):
        png = _render_pdf_page(document, index)
        text = texts[index]
        if need_ocr and png:
            image_path = path.with_name(f".sheet-{index}.png")
            image_path.write_bytes(png)
            try:
                text = (text + "\n" + _ocr(image_path)).strip()
            finally:
                image_path.unlink(missing_ok=True)
        pages.append({"text": text, "png": png})
    return pages


def _render_pdf_page(document, index: int) -> bytes:
    import Quartz
    from Foundation import NSURL
    import tempfile

    page = document.pageAtIndex_(index)
    box = page.boundsForBox_(Quartz.kPDFDisplayBoxMediaBox)
    scale = 1.4
    width = max(1, int(box.size.width * scale))
    height = max(1, int(box.size.height * scale))
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    context = Quartz.CGBitmapContextCreate(None, width, height, 8, 0, space, Quartz.kCGImageAlphaPremultipliedLast)
    Quartz.CGContextSetRGBFillColor(context, 1, 1, 1, 1)
    Quartz.CGContextFillRect(context, Quartz.CGRectMake(0, 0, width, height))
    Quartz.CGContextScaleCTM(context, scale, scale)
    page.drawWithBox_toContext_(Quartz.kPDFDisplayBoxMediaBox, context)
    image = Quartz.CGBitmapContextCreateImage(context)
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    destination = Quartz.CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(str(target)), "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(destination, image, None)
    Quartz.CGImageDestinationFinalize(destination)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data


def _ocr(path: Path) -> str:
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        return ""
    url = NSURL.fileURLWithPath_(str(path))
    request = Vision.VNRecognizeTextRequest.alloc().init()
    try:
        request.setRecognitionLanguages_(["ru-RU", "en-US"])
    except Exception:
        pass
    request.setUsesLanguageCorrection_(False)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    success, _error = handler.performRequests_error_([request], None)
    if not success:
        return ""
    lines = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append(str(candidates[0].string()))
    return "\n".join(lines)
