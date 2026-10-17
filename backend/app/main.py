"""API FastAPI cho ứng dụng tra cứu lộ trình xe buýt (Neo4j)."""
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from neo4j.exceptions import AuthError, ServiceUnavailable

from . import db, repository as repo, routing
from .schemas import (DepartureIn, RouteIn, RouteUpdate, SegmentIn, StationIn, StationUpdate)

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db.verify()
        repo.ensure_schema()
    except Exception as exc:  # vẫn cho server chạy để hiển thị lỗi kết nối rõ ràng qua /api/health
        print(f"[CẢNH BÁO] Chưa kết nối được Neo4j: {exc}")
    yield
    db.close_driver()


app = FastAPI(title="Tra cứu lộ trình xe buýt - Neo4j", version="1.0", lifespan=lifespan)


# ----------------------------------------------------------------------------- xử lý lỗi
@app.exception_handler(repo.NotFound)
async def _nf(_: Request, e: repo.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(e)})


@app.exception_handler(repo.Conflict)
async def _cf(_: Request, e: repo.Conflict):
    return JSONResponse(status_code=409, content={"detail": str(e)})


@app.exception_handler(repo.Invalid)
async def _iv(_: Request, e: repo.Invalid):
    return JSONResponse(status_code=400, content={"detail": str(e)})


@app.exception_handler(routing.RoutingError)
async def _re(_: Request, e: routing.RoutingError):
    return JSONResponse(status_code=400, content={"detail": str(e)})


@app.exception_handler(ServiceUnavailable)
async def _su(_: Request, e: ServiceUnavailable):
    return JSONResponse(status_code=503, content={
        "detail": "Không kết nối được Neo4j. Hãy mở Neo4j Desktop, Start DBMS và kiểm tra file .env."})


@app.exception_handler(AuthError)
async def _ae(_: Request, e: AuthError):
    return JSONResponse(status_code=503, content={
        "detail": "Sai tên đăng nhập/mật khẩu Neo4j. Kiểm tra NEO4J_USER và NEO4J_PASSWORD trong .env."})


@app.exception_handler(Exception)
async def _any(_: Request, e: Exception):
    import traceback
    traceback.print_exception(e)  # in đầy đủ ra cửa sổ terminal đang chạy uvicorn
    return JSONResponse(status_code=500, content={
        "detail": f"Lỗi máy chủ ({type(e).__name__}): {e}"})


# ----------------------------------------------------------------------------- hệ thống
@app.get("/api/health")
def health():
    db.verify()
    return {"status": "ok", **repo.stats()}


@app.get("/api/stats")
def stats():
    return repo.stats()


# ----------------------------------------------------------------------------- trạm
@app.get("/api/stations")
def list_stations(q: Optional[str] = None):
    return repo.list_stations(q)


@app.get("/api/stations/{station_id}")
def get_station(station_id: str):
    return repo.get_station(station_id)


@app.post("/api/stations", status_code=201)
def create_station(body: StationIn):
    return repo.create_station(body.model_dump())


@app.put("/api/stations/{station_id}")
def update_station(station_id: str, body: StationUpdate):
    return repo.update_station(station_id, body.model_dump(exclude_unset=True))


@app.delete("/api/stations/{station_id}", status_code=204)
def delete_station(station_id: str):
    repo.delete_station(station_id)


# ----------------------------------------------------------------------------- tuyến
@app.get("/api/routes")
def list_routes():
    return repo.list_routes()


@app.get("/api/routes/{code}")
def get_route(code: str):
    return repo.get_route(code)


@app.post("/api/routes", status_code=201)
def create_route(body: RouteIn):
    return repo.create_route(body.model_dump())


@app.put("/api/routes/{code}")
def update_route(code: str, body: RouteUpdate):
    return repo.update_route(code, body.model_dump(exclude_unset=True))


@app.delete("/api/routes/{code}", status_code=204)
def delete_route(code: str):
    repo.delete_route(code)


@app.post("/api/routes/{code}/departures")
def add_departure(code: str, body: DepartureIn):
    return repo.add_departure(code, body.direction, body.time)


@app.delete("/api/routes/{code}/departures")
def remove_departure(code: str, time: str, direction: Literal["out", "in"] = "out"):
    return repo.remove_departure(code, direction, time)


@app.put("/api/routes/{code}/segments")
def update_segment(code: str, body: SegmentIn):
    return repo.update_segment(code, body.from_id, body.to_id, body.distance_km, body.time_min)


# ----------------------------------------------------------------------------- tìm đường
Mode = Literal["shortest", "fewest_transfers"]
Metric = Literal["time", "distance"]


@app.get("/api/path")
def path(origin: str, dest: str, mode: Mode = "shortest", metric: Metric = "time",
         initial_wait: bool = True):
    return routing.find_path(repo.get_graph(), origin, dest, mode, metric, initial_wait)


@app.get("/api/path/compare")
def path_compare(origin: str, dest: str, metric: Metric = "time", initial_wait: bool = True):
    return routing.compare(repo.get_graph(), origin, dest, metric, initial_wait)


# ----------------------------------------------------------------------------- đồ thị
@app.get("/api/graph")
def graph(route: Optional[str] = Query(None)):
    return repo.graph_view(route)


# Giao diện web (phải mount sau cùng)
if os.path.isdir(FRONTEND):
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
