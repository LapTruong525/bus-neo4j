"""Kiểm thử tầng API (FastAPI) với đồ thị mẫu nạp sẵn trong RAM, không cần Neo4j."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "seed"))

from app import repository  # noqa: E402
from app.main import app  # noqa: E402
from app.routing import build_graph  # noqa: E402
from data import build_dataset  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    st, rt, ed = build_dataset()
    g = build_graph(st, rt, ed)
    monkeypatch.setattr(repository, "get_graph", lambda: g)
    return TestClient(app), st


def _id(st, name):
    return next(s["id"] for s in st if s["name"] == name)


def test_path_endpoint(client):
    c, st = client
    r = c.get("/api/path", params={"origin": _id(st, "Bến xe Quận 8"),
                                   "dest": _id(st, "Bến xe An Sương"), "mode": "fewest_transfers"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] and body["transfers"] == 1
    assert [leg["route"] for leg in body["legs"]] == ["08", "04"]
    ids = body["path_station_ids"]
    assert all(a != b for a, b in zip(ids, ids[1:]))


def test_compare_endpoint(client):
    c, st = client
    r = c.get("/api/path/compare", params={"origin": _id(st, "Chợ Kim Biên"),
                                           "dest": _id(st, "ĐH Nông Lâm")})
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"shortest", "fewest_transfers"}
    assert j["fewest_transfers"]["transfers"] <= j["shortest"]["transfers"]


def test_bad_requests(client):
    c, st = client
    assert c.get("/api/path", params={"origin": "S01", "dest": "S01"}).status_code == 400
    assert c.get("/api/path", params={"origin": "S01", "dest": "XXX"}).status_code == 400
    assert c.get("/api/path", params={"origin": "S01", "dest": "S02", "mode": "bay"}).status_code == 422


def test_validation(client):
    c, _ = client
    bad_route = {"code": "99", "name": "x", "headway_min": 10, "first_departure": "25:00",
                 "last_departure": "20:00", "stops": ["S01", "S02"]}
    assert c.post("/api/routes", json=bad_route).status_code == 422
    assert c.post("/api/stations", json={"name": "", "lat": 10, "lon": 106}).status_code == 422
    assert c.post("/api/stations", json={"name": "A", "lat": 999, "lon": 106}).status_code == 422
    assert c.post("/api/routes/01/departures", json={"direction": "out", "time": "7h30"}).status_code == 422
