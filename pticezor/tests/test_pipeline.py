from app.pipeline import analyze
from app.scenario import build_demo


def test_demo_clip_opens_cold_points_and_skips_the_warm_sleeper():
    result = analyze(build_demo())
    cells = {(point["zone"], point["cell"]) for point in result["points"]}
    assert ("1", "В3") in cells
    assert ("1", "А2") in cells
    assert ("1", "Г1") not in cells
    assert result["thermal_fault"] is True
    assert result["fault_zones"] == ["2"]
    assert result["weight_hidden"] is False
    assert result["weight_median"] is not None
    assert result["visible"] < result["planted"]
    assert result["visible"] > 0
    assert result["activity_text"] == "ниже обычной"
    assert result["phone"] is True
    hold = next(point for point in result["points"] if point["cell"] == "В3")
    assert hold["delta_c"] >= 4
