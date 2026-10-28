"""Thuật toán tìm đường xe buýt có chuyển tuyến (thuần Python, không phụ thuộc Neo4j).

Mô hình: Dijkstra trên đồ thị TRẠNG THÁI (trạm, tuyến đang đi).
  - Đi tiếp trên cùng tuyến sang trạm kế:  cộng thời gian + khoảng cách của cạnh CONNECTS_TO.
  - Đổi tuyến tại một trạm:                cộng thời gian chờ = headway(tuyến mới) / 2, số lần chuyển + 1.
  - Lên xe lần đầu (tùy chọn):             cộng thời gian chờ = headway(tuyến đầu) / 2.

Mỗi trạng thái mang vector (thời gian, khoảng cách, số lần chuyển). Tùy chế độ, vector được so sánh
theo thứ tự từ điển khác nhau; vì cả ba thành phần đều không âm và cộng dồn nên Dijkstra vẫn đúng.
"""
import heapq
import itertools
from dataclasses import dataclass, field


class RoutingError(ValueError):
    pass


@dataclass
class Graph:
    stations: dict                 # id -> {"id","name","lat","lon",...}
    routes: dict                   # code -> {"code","name","headway_min",...}
    out: dict = field(default_factory=dict)        # (station_id, route) -> [(to_id, dist, time)]
    routes_at: dict = field(default_factory=dict)  # station_id -> set(route)

    def headway(self, route: str) -> float:
        return float(self.routes.get(route, {}).get("headway_min") or 10)


def build_graph(stations, routes, edges) -> Graph:
    g = Graph(
        stations={s["id"]: s for s in stations},
        routes={r["code"]: r for r in routes},
    )
    for e in edges:
        a, b, r = e["from"], e["to"], e["route"]
        g.out.setdefault((a, r), []).append((b, float(e["distance_km"]), float(e["time_min"])))
        g.routes_at.setdefault(a, set()).add(r)
        g.routes_at.setdefault(b, set()).add(r)
    return g


# Thứ tự ưu tiên các thành phần chi phí cho từng chế độ
_ORDERS = {
    ("shortest", "time"): ("time", "transfers", "dist"),
    ("shortest", "distance"): ("dist", "time", "transfers"),
    ("fewest_transfers", "time"): ("transfers", "time", "dist"),
    ("fewest_transfers", "distance"): ("transfers", "dist", "time"),
}


def find_path(g: Graph, origin: str, dest: str, mode: str = "shortest",
              metric: str = "time", initial_wait: bool = True) -> dict:
    """Tìm hành trình tối ưu giữa hai trạm.

    mode:   "shortest"          -> nhỏ nhất theo `metric` (thời gian hoặc khoảng cách)
            "fewest_transfers"  -> ít lần chuyển tuyến nhất, hòa thì chọn theo `metric`
    metric: "time" | "distance"
    """
    if (mode, metric) not in _ORDERS:
        raise RoutingError(f"Chế độ không hợp lệ: mode={mode}, metric={metric}")
    if origin not in g.stations:
        raise RoutingError(f"Không tìm thấy trạm xuất phát: {origin}")
    if dest not in g.stations:
        raise RoutingError(f"Không tìm thấy trạm đích: {dest}")
    if origin == dest:
        raise RoutingError("Trạm xuất phát và trạm đích trùng nhau")

    order = _ORDERS[(mode, metric)]

    def key(vec):  # vec = (time, dist, transfers)
        d = {"time": vec[0], "dist": vec[1], "transfers": vec[2]}
        return tuple(d[k] for k in order)

    counter = itertools.count()
    best, prev, heap = {}, {}, []

    for r in g.routes_at.get(origin, ()):
        w = g.headway(r) / 2 if initial_wait else 0.0
        st = (origin, r)
        vec = (w, 0.0, 0)
        best[st] = vec
        prev[st] = None
        heapq.heappush(heap, (key(vec), next(counter), st))

    goal = None
    while heap:
        k, _, st = heapq.heappop(heap)
        vec = best[st]
        if k > key(vec):
            continue  # bản ghi cũ
        station, route = st
        if station == dest:
            goal = st
            break
        # 1) đi tiếp trên cùng tuyến
        for to, dist, tmin in g.out.get((station, route), ()):
            nst = (to, route)
            nvec = (vec[0] + tmin, vec[1] + dist, vec[2])
            if nst not in best or key(nvec) < key(best[nst]):
                best[nst] = nvec
                prev[nst] = (st, "ride", dist, tmin)
                heapq.heappush(heap, (key(nvec), next(counter), nst))
        # 2) đổi sang tuyến khác tại trạm hiện tại
        for r2 in g.routes_at.get(station, ()):
            if r2 == route:
                continue
            nst = (station, r2)
            wait = g.headway(r2) / 2
            nvec = (vec[0] + wait, vec[1], vec[2] + 1)
            if nst not in best or key(nvec) < key(best[nst]):
                best[nst] = nvec
                prev[nst] = (st, "transfer", 0.0, wait)
                heapq.heappush(heap, (key(nvec), next(counter), nst))

    if goal is None:
        return {"found": False, "mode": mode, "metric": metric, "origin": origin, "dest": dest}

    return _build_result(g, goal, best, prev, mode, metric, origin, dest, initial_wait)


def _build_result(g, goal, best, prev, mode, metric, origin, dest, initial_wait):
    # Truy vết ngược
    chain = []
    st = goal
    while st is not None:
        chain.append(st)
        p = prev[st]
        st = p[0] if p else None
    chain.reverse()

    def info(sid):
        s = g.stations[sid]
        return {"id": sid, "name": s["name"], "lat": s.get("lat"), "lon": s.get("lon")}

    legs = []
    first_route = chain[0][1]
    leg = {
        "route": first_route, "route_name": g.routes[first_route]["name"],
        "wait_min": round(g.headway(first_route) / 2, 1) if initial_wait else 0.0,
        "stops": [info(chain[0][0])], "ride_min": 0.0, "distance_km": 0.0,
    }
    for a, b in zip(chain, chain[1:]):
        kind, dist, tmin = prev[b][1], prev[b][2], prev[b][3]
        if kind == "ride":
            leg["stops"].append(info(b[0]))
            leg["ride_min"] += tmin
            leg["distance_km"] += dist
        else:  # đổi tuyến
            legs.append(leg)
            leg = {
                "route": b[1], "route_name": g.routes[b[1]]["name"],
                "wait_min": round(tmin, 1),
                "stops": [info(b[0])], "ride_min": 0.0, "distance_km": 0.0,
            }
    legs.append(leg)

    for lg in legs:
        lg["ride_min"] = round(lg["ride_min"], 1)
        lg["distance_km"] = round(lg["distance_km"], 2)
        lg["num_stops"] = len(lg["stops"]) - 1
        lg["from"], lg["to"] = lg["stops"][0], lg["stops"][-1]

    total_time, total_dist, transfers = best[goal]
    wait_total = sum(lg["wait_min"] for lg in legs)
    return {
        "found": True, "mode": mode, "metric": metric, "origin": origin, "dest": dest,
        "total_time_min": round(total_time, 1),
        "total_distance_km": round(total_dist, 2),
        "transfers": transfers,
        "ride_time_min": round(sum(lg["ride_min"] for lg in legs), 1),
        "wait_time_min": round(wait_total, 1),
        "num_stops": sum(lg["num_stops"] for lg in legs),
        "legs": legs,
        "path_station_ids": _dedupe([s["id"] for lg in legs for s in lg["stops"]]),
    }


def _dedupe(seq):
    """Bỏ phần tử trùng liền kề (trạm chuyển tuyến xuất hiện ở cuối chặng trước và đầu chặng sau)."""
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def compare(g: Graph, origin: str, dest: str, metric: str = "time", initial_wait: bool = True) -> dict:
    return {
        "shortest": find_path(g, origin, dest, "shortest", metric, initial_wait),
        "fewest_transfers": find_path(g, origin, dest, "fewest_transfers", metric, initial_wait),
    }
