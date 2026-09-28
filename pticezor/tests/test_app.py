import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.ingest import is_night
from app.live import keep_recent
from app.main import app
from app.rules import DeathPoint
from app.store import open_records, save_run, set_mode, state


def test_open_cell_stays_one_record_for_six_hours(tmp_path):
    db = tmp_path / "pticezor.db"
    result = _result("секция", 4)
    result["playback"] = "live"
    result["points"] = [
        {
            "zone": "1",
            "cell": "В3",
            "t_min": 130,
            "t_label": "02:10",
            "delta_c": 5,
            "reason": "hold",
            "cx_cm": 40,
            "cy_cm": 20,
            "track_id": 2,
        }
    ]
    save_run(db, result, "live", keep_marks=True)
    stored = open_records(db, "live")
    assert len(stored) == 1
    again = keep_recent([], stored)
    assert len(again) == 1
    assert again[0].cell == "В3"
    fresh = keep_recent(
        [DeathPoint("1", "В3", 140, 5, "hold", 40, 20, 2)],
        stored,
    )
    assert len(fresh) == 1


def test_night_window_wraps_past_midnight():
    assert is_night(23, 21, 6)
    assert is_night(5, 21, 6)
    assert not is_night(12, 21, 6)
    assert is_night(2, 0, 6)
    assert not is_night(8, 0, 6)


def test_two_modes_keep_their_own_mornings(tmp_path):
    db = tmp_path / "pticezor.db"
    demo = _result("демо", 10)
    live = _result("секция", 4)
    live["playback"] = "live"
    live["accelerated"] = False
    save_run(db, demo, "demo")
    save_run(db, live, "live", keep_marks=True)
    assert state(db, "demo")["visible"] == 10
    assert state(db, "live")["visible"] == 4
    assert set_mode(db, "demo")["mode"] == "demo"
    assert state(db)["visible"] == 10


def test_upload_without_thermal_does_not_invent_deaths(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.DB_PATH", tmp_path / "pticezor.db")
    monkeypatch.setattr("app.main.GENERATED", tmp_path)
    monkeypatch.setattr("app.main.UPLOADS", tmp_path / "uploads")
    clip = tmp_path / "zone.avi"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    for _ in range(12):
        image = np.full((240, 320, 3), 190, np.uint8)
        cv2.ellipse(image, (160, 120), (28, 16), 0, 0, 360, (40, 40, 40), -1)
        cv2.ellipse(image, (60, 50), (20, 14), 0, 0, 360, (40, 40, 40), -1)
        writer.write(image)
    writer.release()
    client = TestClient(app)
    with clip.open("rb") as handle:
        response = client.post(
            "/api/demo/upload",
            files={"zone1": ("zone.avi", handle, "video/avi")},
            data={
                "hall_seconds": "1",
                "teaching": "false",
                "night": "false",
                "planted": "8",
                "age_days": "27",
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ready"] is True
    assert body["points"] == []
    assert "нет теплоканала" in body["heat_note"]


def test_api_pages_are_closed():
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_same_device_cannot_fill_two_roles():
    client = TestClient(app)
    response = client.post(
        "/api/live/start",
        json={
            "zones": [
                {"id": "1", "rgb": 0, "thermal": 0},
                {"id": "2", "rgb": None, "thermal": None},
            ],
            "feeder_cm": 200,
            "feeder_px": 400,
            "night_from": 0,
            "night_to": 6,
            "planted": 8,
            "age_days": 27,
        },
    )
    body = response.json()
    assert body["ok"] is False
    assert "одно устройство" in body["live_error"]


def test_live_start_without_camera_stays_off():
    client = TestClient(app)
    response = client.post(
        "/api/live/start",
        json={
            "zones": [{"id": "1", "rgb": None, "thermal": None}],
            "feeder_cm": 200,
            "feeder_px": 400,
            "night_from": 0,
            "night_to": 6,
            "planted": 8,
            "age_days": 27,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["live_running"] is False
    assert "камера" in body["live_error"].lower()


def test_camera_list_is_a_list(monkeypatch):
    monkeypatch.setattr("app.main.list_cameras", lambda limit=4: [{"index": 0, "label": "Камера 0"}])
    client = TestClient(app)
    response = client.get("/api/cameras")
    assert response.status_code == 200
    assert isinstance(response.json()["cameras"], list)


def test_summary_sheet_is_a_local_pdf(tmp_path, monkeypatch):
    db = tmp_path / "pticezor.db"
    monkeypatch.setattr("app.main.DB_PATH", db)
    client = TestClient(app)
    missing = client.get("/api/report?kind=summary&mode=demo")
    assert missing.status_code == 404
    save_run(db, _result("демо", 10), "demo")
    response = client.get("/api/report?kind=summary&mode=demo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 4000
    walk = client.get("/api/report?kind=walk&mode=demo")
    assert walk.status_code == 200
    assert walk.content.startswith(b"%PDF")


def _result(section: str, visible: int) -> dict:
    return {
        "section": section,
        "planted": 12,
        "age_days": 27,
        "visible": visible,
        "clock": "08:00",
        "weight_median": 1500,
        "weight_norm": 1441,
        "weight_hidden": False,
        "activity_text": "в пределах обычного для этого часа",
        "activity_detail": "замершие 10%",
        "phone": False,
        "thermal_fault": False,
        "frame_count": 2,
        "still_fraction": 0.1,
        "points": [],
        "heat_note": "",
        "detector_note": "",
        "accelerated": True,
        "playback": "frames",
    }
