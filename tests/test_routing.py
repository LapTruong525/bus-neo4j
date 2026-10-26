"""Kiểm thử thuật toán tìm đường trên bộ dữ liệu mẫu (không cần Neo4j)."""
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "seed"))

from app.routing import RoutingError, build_graph, compare, find_path  # noqa: E402
from data import build_dataset  # noqa: E402


@pytest.fixture(scope="module")
def ds():
    return build_dataset()


@pytest.fixture(scope="module")
def g(ds):
    stations, routes, edges = ds
    return build_graph(stations, routes, edges)


def sid(ds, name):
    return next(s["id"] for s in ds[0] if s["name"] == name)


def test_dataset_meets_requirements(ds):
    stations, routes, edges = ds
    assert 50 <= len(stations) <= 80
    assert 5 <= len(routes) <= 10
    assert len(edges) >= 100
    assert all(e["distance_km"] > 0 and e["time_min"] > 0 for e in edges)
    ids = {s["id"] for s in stations}
    assert all(e["from"] in ids and e["to"] in ids for e in edges)


def test_every_station_is_served(ds, g):
    assert all(s["id"] in g.routes_at for s in ds[0])


def test_direct_route_has_no_transfer(ds, g):
    r = find_path(g, sid(ds, "Chợ Bến Thành"), sid(ds, "ĐHQG TP.HCM"), "shortest", "time")
    assert r["found"] and r["transfers"] == 0 and len(r["legs"]) == 1


def test_transfer_needed(ds, g):
    r = find_path(g, sid(ds, "Bến xe Quận 8"), sid(ds, "Bến xe An Sương"), "fewest_transfers")
    assert r["found"] and r["transfers"] >= 1
    assert r["legs"][0]["route"] == "08"
    assert r["legs"][-1]["route"] == "04"
    # các chặng nối khớp nhau tại trạm chuyển
    for a, b in zip(r["legs"], r["legs"][1:]):
        assert a["to"]["id"] == b["from"]["id"]


def test_total_time_consistent(ds, g):
    r = find_path(g, sid(ds, "Bến xe Chợ Lớn"), sid(ds, "ĐHQG TP.HCM"))
    assert r["total_time_min"] == pytest.approx(r["ride_time_min"] + r["wait_time_min"], abs=0.2)


def test_modes_tradeoff(ds, g):
    names = [s["name"] for s in ds[0]]
    ids = [s["id"] for s in ds[0]]
    checked = 0
    for a in ids[::5]:
        for b in ids[2::7]:
            if a == b:
                continue
            c = compare(g, a, b)
            s, f = c["shortest"], c["fewest_transfers"]
            assert s["found"] == f["found"]
            if not s["found"]:
                continue
            # ngắn nhất không chậm hơn; ít chuyển tuyến không chuyển nhiều hơn
            assert s["total_time_min"] <= f["total_time_min"] + 1e-6
            assert f["transfers"] <= s["transfers"]
            checked += 1
    assert checked > 50


def test_distance_metric_not_longer(ds, g):
    a, b = sid(ds, "Bến xe Quận 8"), sid(ds, "Bến xe Miền Tây")
    by_time = find_path(g, a, b, "shortest", "time")
    by_dist = find_path(g, a, b, "shortest", "distance")
    assert by_dist["total_distance_km"] <= by_time["total_distance_km"] + 1e-6


def test_initial_wait_toggle(ds, g):
    a, b = sid(ds, "Chợ Bến Thành"), sid(ds, "Bến xe Chợ Lớn")
    with_wait = find_path(g, a, b, initial_wait=True)
    no_wait = find_path(g, a, b, initial_wait=False)
    assert with_wait["total_time_min"] > no_wait["total_time_min"]


def test_unreachable_and_errors(ds):
    stations, routes, edges = ds
    stations = stations + [{"id": "S99", "name": "Trạm cô lập", "lat": 10.9, "lon": 106.9}]
    g2 = build_graph(stations, routes, edges)
    assert find_path(g2, "S01", "S99")["found"] is False
    with pytest.raises(RoutingError):
        find_path(g2, "S01", "S01")
    with pytest.raises(RoutingError):
        find_path(g2, "S01", "KHONG_TON_TAI")
    with pytest.raises(RoutingError):
        find_path(g2, "S01", "S02", mode="sai")
