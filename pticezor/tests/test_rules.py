import pytest

from app.rules import (
    ActivityReport,
    DeathPoint,
    Detection,
    Frame,
    GapSpot,
    Grid,
    ZoneRect,
    activity_report,
    exclusive_counts,
    find_deaths,
    fit_demo_model,
    in_any_mask,
    median_weight,
    norm_grams,
    pose_label,
    thermal_fault,
)

GRID = Grid()


def bird(tid, x, y, w, h, temp, **kwargs):
    return Detection(tid, x, y, w, h, temp, **kwargs)


def flock(n=6, temp=38.0, t_shift=0.0):
    return [bird(i, 30 + i * 40 + t_shift, 50, 16, 12, temp) for i in range(1, n + 1)]


def frame(t, dets, night=True, **kwargs):
    return Frame(t_min=t, night=night, detections=dets, floor_temp_c=kwargs.pop("floor", 24), **kwargs)


def side_cold(tid=99, x=400, y=180, temp=32.0, **kwargs):
    return bird(tid, x, y, 28, 12, temp, **kwargs)


def times(start, end, step=0.5):
    t = start
    out = []
    while t <= end + 1e-9:
        out.append(round(t, 4))
        t += step
    return out


def test_pose_thresholds():
    assert pose_label(28, 12) == "side"
    assert pose_label(20, 10) == "side"
    assert pose_label(16, 12) == "sit"
    assert pose_label(19, 10) == "undecided"


def test_warm_side_bird_gets_no_point():
    frames = [
        frame(t, flock() + [side_cold(temp=37.5)])
        for t in times(0, 10)
    ]
    assert find_deaths(frames, GRID) == []


def test_night_cold_side_opens_after_ten_minutes():
    frames = [frame(t, flock() + [side_cold()]) for t in times(0, 10)]
    points = find_deaths(frames, GRID)
    assert len(points) == 1
    assert points[0].reason == "hold"
    assert points[0].t_min == pytest.approx(10)
    assert points[0].delta_c == pytest.approx(6)
    assert points[0].cell == "В3"


def test_night_cold_side_under_ten_minutes_stays_closed():
    frames = [frame(t, flock() + [side_cold()]) for t in times(0, 9)]
    assert find_deaths(frames, GRID) == []


def test_night_ignores_motion():
    frames = []
    for t in times(0, 10):
        frames.append(frame(t, flock() + [side_cold(x=400 + t)]))
    points = find_deaths(frames, GRID)
    assert len(points) == 1


def test_sitting_and_undecided_do_not_open():
    sit = [frame(t, flock() + [bird(99, 400, 180, 16, 12, 32)]) for t in times(0, 10)]
    mid = [frame(t, flock() + [bird(99, 400, 180, 19, 10, 32)]) for t in times(0, 10)]
    assert find_deaths(sit, GRID) == []
    assert find_deaths(mid, GRID) == []


def test_day_still_cold_with_walking_neighbors():
    frames = []
    for t in times(0, 15):
        walkers = flock(t_shift=12 * t / 15)
        frames.append(frame(t, walkers + [side_cold()], night=False))
    points = find_deaths(frames, GRID)
    assert len(points) == 1
    assert points[0].reason == "hold"


def test_day_bird_that_moved_is_not_dead():
    frames = []
    for t in times(0, 15):
        walkers = flock(t_shift=12 * t / 15)
        frames.append(frame(t, walkers + [side_cold(x=400 + 8 * t / 15)], night=False))
    assert find_deaths(frames, GRID) == []


def test_day_bbox_change_blocks_point():
    frames = []
    for t in times(0, 15):
        walkers = flock(t_shift=12 * t / 15)
        grown = side_cold()
        grown.w_cm = 28 * (1 + 0.2 * t / 15)
        frames.append(frame(t, walkers + [grown], night=False))
    assert find_deaths(frames, GRID) == []


def test_day_whole_frame_still_is_not_a_carcass_list():
    frames = [frame(t, flock() + [side_cold()], night=False) for t in times(0, 15)]
    assert find_deaths(frames, GRID) == []
    report = activity_report(frames, yesterday_still=0.2, age_days=27)
    assert report.text == "ниже обычной"


def test_thermal_fault_suppresses_points():
    frames = []
    for t in times(0, 10):
        cold = [bird(i, 20 + i * 30, 40, 28, 12, 20) for i in range(6)]
        warm = [bird(i, 20 + i * 30, 120, 16, 12, 40) for i in range(6, 12)]
        frames.append(frame(t, cold + warm, floor=12, floor_baseline_c=24))
    assert thermal_fault(frames[0])
    assert find_deaths(frames, GRID) == []


def test_merged_box_is_not_death():
    frames = [
        frame(t, flock() + [side_cold(merged=True)])
        for t in times(0, 10)
    ]
    assert find_deaths(frames, GRID) == []


def test_lost_track_is_not_death():
    frames = [frame(t, flock() + [side_cold()]) for t in times(0, 8)]
    frames += [frame(t, flock()) for t in times(8.5, 16)]
    assert find_deaths(frames, GRID) == []


def test_gap_cold_spot_opens_immediately():
    gap = GapSpot(200, 30, 32)
    frames = [frame(0, flock(), gap_spots=[gap])]
    points = find_deaths(frames, GRID)
    assert len(points) == 1
    assert points[0].reason == "gap"
    assert points[0].t_min == 0
    assert points[0].cell == "А2"
    assert points[0].delta_c == pytest.approx(6)


def test_gap_during_fault_does_not_open():
    cold = [bird(i, 20 + i * 30, 40, 28, 12, 20) for i in range(6)]
    warm = [bird(i, 20 + i * 30, 120, 16, 12, 40) for i in range(6, 12)]
    gap = GapSpot(200, 30, 10)
    frames = [frame(0, cold + warm, floor=12, floor_baseline_c=24, gap_spots=[gap])]
    assert find_deaths(frames, GRID) == []


def test_occlusion_recheck_waits_fifteen_minutes_after_feeder_stops():
    live = flock()
    frames = [
        frame(0, live, feeder_on=True, occluded_cells=["Б2"]),
        frame(5, live, feeder_on=True, occluded_cells=["Б2"]),
        frame(6, live, feeder_on=False),
        frame(20, live, feeder_on=False),
        frame(21, live + [side_cold(x=200, y=100)], feeder_on=False),
    ]
    points = find_deaths(frames, GRID)
    assert len(points) == 1
    assert points[0].reason == "recheck"
    assert points[0].cell == "Б2"
    assert points[0].t_min == pytest.approx(21)


def test_same_cell_does_not_open_twice_within_six_hours():
    existing = [
        DeathPoint("1", "В3", 0, 6, "hold", 400, 180, 99),
    ]
    frames = [frame(t, flock() + [side_cold()]) for t in times(30, 40)]
    assert find_deaths(frames, GRID, existing) == []


def test_weight_median_skips_edge_merged_and_young_chicks():
    model = fit_demo_model()
    good = bird(1, 100, 100, 18, 10, 38)
    edge = bird(2, 5, 5, 30, 20, 38, edge=True)
    merged = bird(3, 80, 80, 40, 30, 38, merged=True)
    only_good = median_weight([good, edge, merged], 27, model)
    assert only_good == pytest.approx(median_weight([good], 27, model))
    assert median_weight([good], 4, model) is None
    assert median_weight([edge, merged], 27, model) is None
    assert norm_grams(27) == pytest.approx(943 + (1524 - 943) * 6 / 7)


def test_activity_threshold_and_first_day():
    still_spots = [(80, 40), (240, 50), (80, 180), (400, 180)]
    move_spots = [(80, 100), (240, 140), (400, 40), (320, 140)]
    frames = []
    for t in times(120, 130):
        dets = [bird(i + 1, x, y, 16, 12, 38) for i, (x, y) in enumerate(still_spots)]
        dets += [
            bird(i + 5, x + 8 * (t - 120), y, 16, 12, 38)
            for i, (x, y) in enumerate(move_spots)
        ]
        frames.append(frame(t, dets))
    report = activity_report(frames, yesterday_still=0.2, age_days=27)
    assert isinstance(report, ActivityReport)
    assert report.text == "ниже обычной"
    assert report.phone is True
    first = activity_report(frames, yesterday_still=0.2, age_days=1)
    assert first.phone is False
    assert "первые сутки" in first.text
    quiet = activity_report(frames, yesterday_still=report.still_fraction, age_days=27)
    assert quiet.text == "в пределах обычного для этого часа"
    assert quiet.phone is False


def test_wall_gathering_without_activity_drop():
    frames = []
    for t in times(0, 10):
        dets = [bird(i, 12 + 0.7 * t, 12 + i, 16, 12, 38) for i in range(8)]
        dets += [bird(20, 200 + 0.7 * t, 140, 16, 12, 38), bird(21, 220 + 0.7 * t, 150, 16, 12, 38)]
        frames.append(frame(t, dets, width_cm=480, height_cm=270))
    report = activity_report(frames, yesterday_still=0.0, age_days=10)
    assert report.text == "птица собралась у стены"
    assert report.phone is True


def test_overlap_is_counted_once():
    zones = [
        ZoneRect("1", 0, 0, 100, 50, priority=0),
        ZoneRect("2", 80, 0, 180, 50, priority=1),
    ]
    counts = exclusive_counts([(90, 10), (120, 10), (10, 10)], zones)
    assert counts == {"1": 2, "2": 1}
    assert sum(counts.values()) == 3


def test_feeder_mask_contains_pan():
    pan = [(100, 100), (160, 100), (160, 140), (100, 140)]
    assert in_any_mask(120, 120, [pan])
    assert not in_any_mask(20, 20, [pan])
