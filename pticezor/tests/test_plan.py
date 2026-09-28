"""Разбор схемы и расстановка камер."""

from fastapi.testclient import TestClient

from app.assign import assign_cameras
from app.hall import hall_plan, toggle_bay
from app.main import _zone_report, app
from app.plan_import import assemble_chain, parse_sheet_text
from app.store import remember_hour, save_run, state

OSOBINO = """
Птичник родительского стада
РУП Белоруснефть-Особино
цех Сож
А Б Г Е Ж
6000
500
""" + "\n".join(["6000"] * 15) + """
4500
6000
6000
4500
2100
Площадь застройки 2026,56
"""


def test_sheet_chain_keeps_the_half_meter_when_the_total_is_read():
    hits = []
    position = 0.0
    for index in range(16):
        hits.append((position, 6000))
        position += 0.08 if index == 0 else 0.05
    hits.append((0.4, 96500))
    chain = assemble_chain([(pos, value) for pos, value in hits if value <= 15000], 96500, least=6, drop_strays=True)
    assert chain == [6000, 500] + [6000] * 15
    assert sum(chain) == 96500


def test_width_chain_keeps_both_bay_sizes():
    from app.plan_import import assemble_chain as chain

    assert chain([(0, 4500), (1, 6000), (2, 6000), (3, 4500)], None, least=2) == [4500, 6000, 6000, 4500]


def test_osobino_chain_builds_the_hall():
    parsed = parse_sheet_text(OSOBINO, "38.23-1+6")
    plan = parsed["plan"]
    assert parsed["needs_confirm"] is False
    assert plan["length_m"] == 96.5
    assert plan["width_m"] == 21.0
    assert plan["vestibule_m"] == [0.0, 6.5]
    assert plan["axes_y"] == ["А", "Б", "Г", "Е", "Ж"]
    assert len(plan["zones"]) == 2
    assert plan["nest"]["h_m"] == 2.1


def test_crooked_sheet_does_not_draw_a_hall():
    parsed = parse_sheet_text("12\n99\nпривет\n3")
    assert parsed["plan"] is None
    assert parsed["needs_confirm"] is True
    assert parsed["fields"] == {
        "length_m": None,
        "width_m": None,
        "vestibule_m": None,
        "zones": None,
    }


def test_confirm_saves_measures_without_inventing_a_chain(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.DB_PATH", tmp_path / "pticezor.db")
    client = TestClient(app)
    response = client.post(
        "/api/hall/confirm",
        json={"length_m": 96.5, "width_m": 21, "vestibule_m": 6.5, "zones": 2},
    )
    assert response.status_code == 200
    hall = response.json()["hall"]
    assert hall["length_m"] == 96.5
    assert hall["width_m"] == 21
    assert len(hall["zones"]) == 2


def test_seventh_zone_is_refused():
    plan = hall_plan()
    message = ""
    for bay in plan["bays"]:
        if any(abs(zone["x_m"] - bay["x_m"]) < 0.2 for zone in plan["zones"]):
            continue
        plan, message = toggle_bay(plan, bay["index"])
        if message:
            break
    assert len(plan["zones"]) == 6
    assert message


def test_state_lists_recorded_hours(tmp_path):
    db = tmp_path / "pticezor.db"
    save_run(db, {
        "section": "демо",
        "planted": 12,
        "age_days": 27,
        "visible": 10,
        "clock": "08:00",
        "weight_median": 1500,
        "weight_norm": 1441,
        "weight_hidden": False,
        "activity_text": "в пределах обычного для этого часа",
        "activity_detail": "",
        "phone": False,
        "thermal_fault": False,
        "frame_count": 2,
        "still_fraction": 0.43,
        "points": [],
        "heat_note": "",
        "detector_note": "",
        "accelerated": True,
        "playback": "frames",
    }, "demo")
    remember_hour(db, "demo", "2026-09-28", 8, 0.2)
    remember_hour(db, "demo", "2026-09-28", 9, 0.5)
    body = state(db, "demo")
    assert body["activity"]["still"] == 0.43
    assert [row["hour"] for row in body["hours"]] == [8, 9]


def test_zone_report_counts_points_of_that_zone():
    report = _zone_report(
        {
            "zones": ["1", "2"],
            "fault_zones": ["2"],
            "points": [
                {"zone": "1", "status": "pending"},
                {"zone": "1", "status": "dead"},
                {"zone": "2", "status": "alive"},
            ],
        },
        {"zones": [{"id": "1", "bay": "8–9"}, {"id": "2", "bay": "9–10"}]},
    )
    assert report[0]["bay"] == "8–9"
    assert report[0]["pending"] == 1 and report[0]["dead"] == 1
    assert report[1]["fault"] is True and report[1]["alive"] == 1


def test_technology_sheet_reads_the_osobino_hall():
    from pathlib import Path

    from app.plan_import import read_plan

    root = Path(__file__).resolve().parents[2]
    sheet = next(root.glob("*ТХ*.pdf"), None)
    if sheet is None:
        return
    plan = read_plan(sheet)["plan"]
    assert plan["length_m"] == 96.5
    assert plan["width_m"] == 21.0
    assert plan["vestibule_m"] == [0.0, 6.5]
    assert plan["axes_y"] == ["А", "Б", "В", "Г", "Д", "Е", "Ж"]
    assert [(item["y_m"], item["h_m"]) for item in plan["nests"]] == [(7.2, 2.7), (11.1, 2.7)]


def test_two_cameras_take_zones_and_the_third_is_thermal():
    rows = assign_cameras(["1", "2"], [{"index": 0}, {"index": 1}, {"index": 2}])
    assert rows == [
        {"id": "1", "rgb": 0, "thermal": 2},
        {"id": "2", "rgb": 1, "thermal": None},
    ]
