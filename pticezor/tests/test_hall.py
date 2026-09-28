"""План общего зала сверяется с чертежом 38.23-1+6."""

from app.hall import hall_plan


def test_osobino_hall_matches_the_drawing():
    plan = hall_plan()
    assert plan["length_m"] == 96.5
    assert plan["width_m"] == 21.0
    assert round(plan["length_m"] * plan["width_m"], 2) == 2026.5
    assert plan["axes_x"][0] == "1" and plan["axes_x"][-1] == "18"
    assert plan["axes_y"] == ["А", "Б", "В", "Г", "Д", "Е", "Ж"]
    assert plan["y_m"] == [0.0, 4.5, 6.0, 10.5, 15.0, 16.5, 21.0]
    assert [(item["y_m"], item["h_m"]) for item in plan["nests"]] == [(7.2, 2.7), (11.1, 2.7)]
    assert all(line < 7.2 or 9.9 < line < 11.1 or line > 13.8 for line in plan["lines_y_m"])
    assert plan["x_m"][2] == 6.5
    first, second = plan["zones"]
    assert first["x_m"] >= plan["vestibule_m"][1]
    assert first["x_m"] + first["w_m"] <= second["x_m"]
    assert second["x_m"] + second["w_m"] <= plan["length_m"]
    assert first["y_m"] + first["h_m"] <= plan["y_m"][1]
    assert second["y_m"] + second["h_m"] <= plan["y_m"][1]
