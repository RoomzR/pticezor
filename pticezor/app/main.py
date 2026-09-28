"""Локальный движок окна «Птицезор». Адрес наружу не показывается."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.assign import assign_cameras
from app.hall import hall_plan, plan_from_totals, toggle_bay
from app.ingest import clip_from_files
from app.live import LIVE_DIR, LiveSession, list_cameras
from app.pipeline import GENERATED, analyze, note_without_yesterday, process_demo, write_frames
from app.plan_import import read_plan
from app.report import build_report
from app.store import load_hall, mark_point, save_hall, save_run, set_mode, state, update_flock

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = GENERATED / "pticezor.db"
STATIC = ROOT / "app" / "static"
UPLOADS = GENERATED / "uploads"
SHEET = GENERATED / "hall" / "sheet.jpg"

app = FastAPI(title="Птицезор", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
SESSION = LiveSession(DB_PATH)


class MarkIn(BaseModel):
    status: str = Field(pattern="^(dead|alive)$")


class ModeIn(BaseModel):
    mode: str = Field(pattern="^(demo|live)$")


class FlockIn(BaseModel):
    planted: int | None = None
    control_grams: float | None = None
    age_days: int | None = None


class ZoneIn(BaseModel):
    id: str
    rgb: int | None = None
    thermal: int | None = None


class LiveIn(BaseModel):
    zones: list[ZoneIn]
    feeder_cm: float = 200
    feeder_px: float = 400
    night_from: int = 0
    night_to: int = 6
    planted: int = 32
    age_days: int = 27
    line_on: bool = False
    mask_pan: bool = True


class LineIn(BaseModel):
    on: bool


class HallConfirm(BaseModel):
    length_m: float
    width_m: float
    vestibule_m: float
    zones: int = Field(ge=1, le=6)


class BayIn(BaseModel):
    index: int


class CameraIn(BaseModel):
    index: int
    label: str = ""


class AssignIn(BaseModel):
    cameras: list[CameraIn] = Field(default_factory=list)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def api_state(mode: str | None = None):
    return _decorate(state(DB_PATH, mode))


@app.get("/api/report")
def api_report(kind: str = "summary", mode: str = "demo"):
    if kind not in {"summary", "walk"} or mode not in {"demo", "live"}:
        raise HTTPException(status_code=400, detail="Нужен лист сводки или обхода.")
    payload = _decorate(state(DB_PATH, mode))
    if kind == "summary" and not payload.get("ready"):
        raise HTTPException(status_code=404, detail="Сводка откроется после показа.")
    name = "Птицезор-обход.pdf" if kind == "walk" else "Птицезор-сводка.pdf"
    pdf = build_report(payload, kind)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


@app.post("/api/mode")
def api_mode(body: ModeIn):
    return _decorate(set_mode(DB_PATH, body.mode))


@app.post("/api/demo/builtin")
def api_builtin():
    result = process_demo(GENERATED / "demo")
    save_run(DB_PATH, result, "demo")
    return _decorate(state(DB_PATH, "demo"))


@app.post("/api/demo/upload")
async def api_upload(
    zone1: UploadFile = File(...),
    zone2: UploadFile | None = File(None),
    thermal: UploadFile | None = File(None),
    hall_seconds: float = Form(1),
    teaching: str = Form("false"),
    night: str = Form("false"),
    planted: int = Form(32),
    age_days: int = Form(27),
):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    zone1_path = _save_upload(zone1, "zone1")
    zone2_path = _save_upload(zone2, "zone2") if zone2 is not None and zone2.filename else None
    thermal_path = _save_upload(thermal, "thermal") if thermal is not None and thermal.filename else None
    try:
        clip = clip_from_files(
            zone1_path,
            zone2_path,
            thermal_path,
            max(hall_seconds, 0.1),
            teaching == "true",
            night == "true",
            planted,
            age_days,
        )
        result = note_without_yesterday(analyze(clip))
        write_frames(clip, result, GENERATED / "demo")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_run(DB_PATH, result, "demo")
    return _decorate(state(DB_PATH, "demo"))


@app.get("/api/cameras")
def api_cameras():
    if SESSION.running:
        return {"cameras": [], "busy": True}
    return {"cameras": list_cameras(limit=8), "busy": False}


@app.post("/api/cameras/assign")
def api_assign(body: AssignIn):
    hall = _hall()
    rows = assign_cameras([zone["id"] for zone in hall.get("zones") or []], [item.model_dump() for item in body.cameras])
    return {"zones": rows}


@app.post("/api/hall/upload")
async def api_hall_upload(sheet: UploadFile = File(...)):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    suffix = Path(sheet.filename or "plan.pdf").suffix.lower() or ".pdf"
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Нужен PDF или картинка плана.")
    target = UPLOADS / f"hall{suffix}"
    with target.open("wb") as handle:
        shutil.copyfileobj(sheet.file, handle)
    parsed = read_plan(target)
    _keep_sheet(parsed.get("png") or b"")
    plan = parsed.get("plan")
    if plan is not None:
        save_hall(DB_PATH, plan)
        return {"ok": True, "needs_confirm": False, "hall": plan}
    return {"ok": False, "needs_confirm": True, "fields": parsed["fields"], "sheet": SHEET.exists()}


@app.post("/api/hall/confirm")
def api_hall_confirm(body: HallConfirm):
    try:
        plan = plan_from_totals(body.length_m, body.width_m, body.vestibule_m, body.zones)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_hall(DB_PATH, plan)
    return _decorate(state(DB_PATH))


@app.post("/api/hall/bay")
def api_hall_bay(body: BayIn):
    plan, message = toggle_bay(_hall(), body.index)
    if message:
        return {"ok": False, "error": message, "hall": plan}
    save_hall(DB_PATH, plan)
    payload = _decorate(state(DB_PATH))
    payload["ok"] = True
    return payload


@app.get("/api/hall/sheet")
def api_hall_sheet():
    if not SHEET.exists():
        raise HTTPException(status_code=404)
    return FileResponse(SHEET)


@app.post("/api/live/start")
def api_live_start(body: LiveIn):
    problem = _camera_conflict(body)
    if problem:
        return {"ok": False, "live_running": SESSION.running, "live_error": problem}
    SESSION.start(body.model_dump())
    return {"ok": SESSION.running, "live_running": SESSION.running, "live_error": SESSION.error}


@app.post("/api/live/line")
def api_line(body: LineIn):
    SESSION.set_line(body.on)
    return {"line_on": SESSION.line_on}


@app.post("/api/live/stop")
def api_live_stop():
    SESSION.stop()
    return _decorate(state(DB_PATH, "live"))


@app.get("/api/live/preview/{zone}")
def api_preview(zone: str):
    if not _zone_name(zone):
        raise HTTPException(status_code=404)
    path = LIVE_DIR / f"zone{zone}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.post("/api/points/{point_id}/mark")
def api_mark(point_id: int, body: MarkIn):
    try:
        return _decorate(mark_point(DB_PATH, point_id, body.status))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Точка не найдена") from exc


@app.post("/api/flock")
def api_flock(body: FlockIn, mode: str = "demo"):
    try:
        return _decorate(update_flock(DB_PATH, mode, body.planted, body.control_grams, body.age_days))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Сначала откройте показ или пустите камеры") from exc


@app.get("/media/{mode}/{zone}/{frame}")
def media(mode: str, zone: str, frame: int):
    if mode not in {"demo", "live"} or not _zone_name(zone):
        raise HTTPException(status_code=404)
    path = GENERATED / mode / f"zone{zone}" / f"{frame:05d}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


def _hall() -> dict:
    return load_hall(DB_PATH) or hall_plan()


def _zone_report(payload: dict, hall: dict) -> list[dict]:
    bays = {str(zone["id"]): zone.get("bay") or "" for zone in hall.get("zones") or []}
    ids = payload.get("zones") or list(bays)
    faults = {str(zone) for zone in payload.get("fault_zones") or []}
    points = payload.get("points") or []
    report = []
    for zone_id in ids:
        own = [point for point in points if str(point.get("zone")) == str(zone_id)]
        report.append({
            "id": str(zone_id),
            "bay": bays.get(str(zone_id), ""),
            "pending": sum(1 for point in own if point["status"] == "pending"),
            "dead": sum(1 for point in own if point["status"] == "dead"),
            "alive": sum(1 for point in own if point["status"] == "alive"),
            "fault": str(zone_id) in faults,
        })
    return report


def _decorate(payload: dict) -> dict:
    hall = _hall()
    payload["hall"] = hall
    payload["zone_report"] = _zone_report(payload, hall)
    payload["live_running"] = SESSION.running
    payload["live_error"] = SESSION.error
    payload["line_on"] = SESSION.line_on
    payload["preview"] = {
        zone["id"]: (LIVE_DIR / f"zone{zone['id']}.jpg").exists()
        for zone in hall.get("zones") or []
    }
    return payload


def _zone_name(zone: str) -> bool:
    return zone.isdigit() and 1 <= int(zone) <= 6


def _keep_sheet(png: bytes) -> None:
    if not png:
        return
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return
        cv2.imwrite(str(SHEET), image)
    except Exception:
        SHEET.write_bytes(png)


def _camera_conflict(body: LiveIn) -> str:
    used: list[int] = []
    for zone in body.zones:
        if zone.rgb is None:
            continue
        if zone.thermal is not None and zone.thermal == zone.rgb:
            return f"В зоне {zone.id} тепловизор и обычная камера — одно устройство. Выберите разные."
        if zone.rgb in used or (zone.thermal is not None and zone.thermal in used):
            return "Одно устройство выбрано дважды. У каждой зоны своя камера."
        used.append(zone.rgb)
        if zone.thermal is not None:
            used.append(zone.thermal)
    return ""


def _save_upload(upload: UploadFile, name: str) -> Path:
    suffix = Path(upload.filename or "clip.mp4").suffix or ".mp4"
    target = UPLOADS / f"{name}{suffix}"
    with target.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return target
