"""Tầng truy cập dữ liệu: toàn bộ truy vấn Cypher nằm ở đây.

Mô hình đồ thị:
  (:Station {id, name, district, lat, lon})
  (:BusRoute {code, name, headway_min, first_departure, last_departure, color,
              departures_out[], departures_in[]})
  (:BusRoute)-[:STOPS_AT {seq}]->(:Station)                      thứ tự các trạm của tuyến
  (:Station)-[:CONNECTS_TO {route, distance_km, time_min}]->(:Station)   đoạn đường có hướng, có trọng số
"""
import threading

from . import db, routing
from .geo import gen_departures, segment_metrics


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


# ----------------------------------------------------------------------------- bộ nhớ đệm đồ thị
_lock = threading.Lock()
_graph = None


def invalidate_graph():
    global _graph
    with _lock:
        _graph = None


def get_graph() -> routing.Graph:
    """Nạp đồ thị từ Neo4j (bằng Cypher) và giữ trong RAM đến khi dữ liệu bị thay đổi."""
    global _graph
    with _lock:
        if _graph is not None:
            return _graph
    stations = [r["s"] for r in db.read("MATCH (s:Station) RETURN s {.*} AS s")]
    routes = [r for r in db.read(
        "MATCH (r:BusRoute) RETURN r.code AS code, r.name AS name, r.headway_min AS headway_min")]
    edges = db.read(
        "MATCH (a:Station)-[e:CONNECTS_TO]->(b:Station) "
        "RETURN a.id AS `from`, b.id AS to, e.route AS route, "
        "e.distance_km AS distance_km, e.time_min AS time_min")
    g = routing.build_graph(stations, routes, edges)
    with _lock:
        _graph = g
    return g


# ----------------------------------------------------------------------------- khởi tạo
def ensure_schema():
    db.write(lambda tx: tx.run(
        "CREATE CONSTRAINT station_id IF NOT EXISTS FOR (s:Station) REQUIRE s.id IS UNIQUE").consume())
    db.write(lambda tx: tx.run(
        "CREATE CONSTRAINT route_code IF NOT EXISTS FOR (r:BusRoute) REQUIRE r.code IS UNIQUE").consume())


def stats():
    return {
        "stations": db.read("MATCH (s:Station) RETURN count(s) AS n")[0]["n"],
        "routes": db.read("MATCH (r:BusRoute) RETURN count(r) AS n")[0]["n"],
        "edges": db.read("MATCH ()-[e:CONNECTS_TO]->() RETURN count(e) AS n")[0]["n"],
    }


# ----------------------------------------------------------------------------- TRẠM
def list_stations(q: str | None = None):
    rows = db.read(
        """
        MATCH (s:Station)
        WHERE $q IS NULL OR toLower(s.name) CONTAINS toLower($q)
              OR toLower(s.district) CONTAINS toLower($q)
        OPTIONAL MATCH (r:BusRoute)-[:STOPS_AT]->(s)
        WITH s, r ORDER BY r.code
        WITH s, collect(DISTINCT r.code) AS routes
        RETURN s {.*, routes: routes} AS station
        ORDER BY s.name
        """,
        q=q or None,
    )
    return [r["station"] for r in rows]


def get_station(station_id: str):
    rows = db.read(
        """
        MATCH (s:Station {id: $id})
        OPTIONAL MATCH (r:BusRoute)-[:STOPS_AT]->(s)
        WITH s, r ORDER BY r.code
        WITH s, collect(DISTINCT r.code) AS routes
        RETURN s {.*, routes: routes} AS station
        """,
        id=station_id,
    )
    if not rows or rows[0]["station"] is None:
        raise NotFound(f"Không tìm thấy trạm {station_id}")
    return rows[0]["station"]


def create_station(data: dict):
    def work(tx):
        if data.get("id"):
            new_id = data["id"]
            if tx.run("MATCH (s:Station {id:$id}) RETURN s", id=new_id).single():
                raise Conflict(f"Mã trạm {new_id} đã tồn tại")
        else:
            row = tx.run(
                "MATCH (s:Station) RETURN max(toInteger(substring(s.id, 1))) AS m").single()
            new_id = f"S{(row['m'] or 0) + 1:02d}"
        tx.run(
            "CREATE (s:Station {id:$id, name:$name, district:$district, lat:$lat, lon:$lon})",
            id=new_id, name=data["name"], district=data.get("district") or "",
            lat=data["lat"], lon=data["lon"],
        ).consume()
        return new_id

    new_id = db.write(work)
    invalidate_graph()
    return get_station(new_id)


def update_station(station_id: str, data: dict):
    props = {k: v for k, v in data.items() if v is not None and k in ("name", "district", "lat", "lon")}

    def work(tx):
        if not tx.run("MATCH (s:Station {id:$id}) RETURN s", id=station_id).single():
            raise NotFound(f"Không tìm thấy trạm {station_id}")
        if props:
            tx.run("MATCH (s:Station {id:$id}) SET s += $props", id=station_id, props=props).consume()
        if "lat" in props or "lon" in props:
            # Tọa độ đổi -> tính lại trọng số các cạnh kề trạm này
            edges = tx.run(
                """
                MATCH (a:Station)-[e:CONNECTS_TO]->(b:Station)
                WHERE a.id = $id OR b.id = $id
                RETURN a.id AS a, b.id AS b, e.route AS route,
                       a.lat AS alat, a.lon AS alon, b.lat AS blat, b.lon AS blon
                """,
                id=station_id,
            ).data()
            upd = []
            for e in edges:
                d, t = segment_metrics(e["alat"], e["alon"], e["blat"], e["blon"])
                upd.append({"a": e["a"], "b": e["b"], "route": e["route"], "d": d, "t": t})
            tx.run(
                """
                UNWIND $rows AS row
                MATCH (a:Station {id: row.a})-[e:CONNECTS_TO {route: row.route}]->(b:Station {id: row.b})
                SET e.distance_km = row.d, e.time_min = row.t
                """,
                rows=upd,
            ).consume()

    db.write(work)
    invalidate_graph()
    return get_station(station_id)


def delete_station(station_id: str):
    """Xóa trạm; các tuyến đi qua trạm được nối lại (trạm trước -> trạm sau)."""
    def work(tx):
        if not tx.run("MATCH (s:Station {id:$id}) RETURN s", id=station_id).single():
            raise NotFound(f"Không tìm thấy trạm {station_id}")
        codes = [r["code"] for r in tx.run(
            "MATCH (r:BusRoute)-[:STOPS_AT]->(:Station {id:$id}) RETURN r.code AS code", id=station_id)]
        for code in codes:
            stops = _route_stop_ids(tx, code)
            _apply_route_stops(tx, code, [s for s in stops if s != station_id])
        tx.run("MATCH (s:Station {id:$id}) DETACH DELETE s", id=station_id).consume()

    db.write(work)
    invalidate_graph()


# ----------------------------------------------------------------------------- TUYẾN
_ROUTE_PROPS = "{.code, .name, .headway_min, .first_departure, .last_departure, .color}"


def list_routes():
    rows = db.read(
        f"""
        MATCH (r:BusRoute)
        OPTIONAL MATCH (r)-[st:STOPS_AT]->(s:Station)
        WITH r, s, st ORDER BY st.seq
        WITH r, collect(s.name) AS names
        RETURN r {_ROUTE_PROPS} AS route, names
        ORDER BY r.code
        """
    )
    out = []
    for row in rows:
        route = row["route"]
        route["num_stops"] = len(row["names"])
        route["first_stop"] = row["names"][0] if row["names"] else None
        route["last_stop"] = row["names"][-1] if row["names"] else None
        out.append(route)
    return out


def get_route(code: str):
    rows = db.read(
        """
        MATCH (r:BusRoute {code: $code})
        OPTIONAL MATCH (r)-[st:STOPS_AT]->(s:Station)
        WITH r, s, st ORDER BY st.seq
        RETURN r {.*} AS route,
               collect(CASE WHEN s IS NULL THEN null ELSE
                   {id: s.id, name: s.name, district: s.district, lat: s.lat, lon: s.lon, seq: st.seq} END) AS stops
        """,
        code=code,
    )
    if not rows or rows[0]["route"] is None:
        raise NotFound(f"Không tìm thấy tuyến {code}")
    route = rows[0]["route"]
    route["stops"] = [s for s in rows[0]["stops"] if s]
    route["segments"] = db.read(
        """
        MATCH (r:BusRoute {code: $code})-[sa:STOPS_AT]->(a:Station)
        MATCH (r)-[sb:STOPS_AT]->(b:Station)
        WHERE sb.seq = sa.seq + 1
        MATCH (a)-[e:CONNECTS_TO {route: $code}]->(b)
        RETURN a.id AS from_id, a.name AS from_name, b.id AS to_id, b.name AS to_name,
               e.distance_km AS distance_km, e.time_min AS time_min
        ORDER BY sa.seq
        """,
        code=code,
    )
    return route


def _route_stop_ids(tx, code):
    return [r["id"] for r in tx.run(
        "MATCH (:BusRoute {code:$code})-[st:STOPS_AT]->(s:Station) RETURN s.id AS id ORDER BY st.seq",
        code=code)]


def _apply_route_stops(tx, code: str, stop_ids: list):
    """Thay toàn bộ danh sách trạm của tuyến: dựng lại STOPS_AT và CONNECTS_TO hai chiều.

    Trọng số của cặp trạm đã có sẵn được giữ nguyên; cặp mới được ước lượng theo tọa độ.
    """
    if len(set(stop_ids)) != len(stop_ids):
        raise Invalid("Một tuyến không được đi qua cùng một trạm hai lần")
    coords = {r["id"]: r for r in tx.run(
        "UNWIND $ids AS i MATCH (s:Station {id:i}) RETURN s.id AS id, s.lat AS lat, s.lon AS lon",
        ids=stop_ids)}
    missing = [i for i in stop_ids if i not in coords]
    if missing:
        raise Invalid(f"Trạm không tồn tại: {', '.join(missing)}")

    old = {(r["a"], r["b"]): (r["d"], r["t"]) for r in tx.run(
        """
        MATCH (a:Station)-[e:CONNECTS_TO {route:$code}]->(b:Station)
        RETURN a.id AS a, b.id AS b, e.distance_km AS d, e.time_min AS t
        """, code=code)}

    tx.run("MATCH ()-[e:CONNECTS_TO {route:$code}]->() DELETE e", code=code).consume()
    tx.run("MATCH (:BusRoute {code:$code})-[st:STOPS_AT]->() DELETE st", code=code).consume()

    if stop_ids:
        tx.run(
            """
            MATCH (r:BusRoute {code:$code})
            UNWIND range(0, size($ids)-1) AS i
            MATCH (s:Station {id: $ids[i]})
            CREATE (r)-[:STOPS_AT {seq: i}]->(s)
            """, code=code, ids=stop_ids).consume()

    rows = []
    for a, b in zip(stop_ids, stop_ids[1:]):
        if (a, b) in old:
            d, t = old[(a, b)]
        elif (b, a) in old:
            d, t = old[(b, a)]
        else:
            d, t = segment_metrics(coords[a]["lat"], coords[a]["lon"], coords[b]["lat"], coords[b]["lon"])
        rows.append({"a": a, "b": b, "d": d, "t": t})
    if rows:
        tx.run(
            """
            UNWIND $rows AS row
            MATCH (a:Station {id: row.a}), (b:Station {id: row.b})
            CREATE (a)-[:CONNECTS_TO {route:$code, distance_km: row.d, time_min: row.t}]->(b)
            CREATE (b)-[:CONNECTS_TO {route:$code, distance_km: row.d, time_min: row.t}]->(a)
            """, rows=rows, code=code).consume()


def create_route(data: dict):
    code = data["code"]
    stops = data.get("stops") or []
    if len(stops) < 2:
        raise Invalid("Tuyến cần ít nhất 2 trạm")
    deps = gen_departures(data["first_departure"], data["last_departure"], data["headway_min"])

    def work(tx):
        if tx.run("MATCH (r:BusRoute {code:$code}) RETURN r", code=code).single():
            raise Conflict(f"Tuyến {code} đã tồn tại")
        tx.run(
            """
            CREATE (r:BusRoute {code:$code, name:$name, headway_min:$headway, first_departure:$first,
                                last_departure:$last, color:$color,
                                departures_out:$deps, departures_in:$deps})
            """,
            code=code, name=data["name"], headway=data["headway_min"], first=data["first_departure"],
            last=data["last_departure"], color=data.get("color") or "#2563eb", deps=deps,
        ).consume()
        _apply_route_stops(tx, code, stops)

    db.write(work)
    invalidate_graph()
    return get_route(code)


def update_route(code: str, data: dict):
    props = {k: v for k, v in data.items()
             if v is not None and k in ("name", "headway_min", "first_departure", "last_departure", "color")}
    stops = data.get("stops")

    def work(tx):
        row = tx.run("MATCH (r:BusRoute {code:$code}) RETURN r {.*} AS r", code=code).single()
        if not row:
            raise NotFound(f"Không tìm thấy tuyến {code}")
        cur = row["r"]
        if any(k in props for k in ("headway_min", "first_departure", "last_departure")):
            deps = gen_departures(
                props.get("first_departure", cur["first_departure"]),
                props.get("last_departure", cur["last_departure"]),
                props.get("headway_min", cur["headway_min"]),
            )
            props["departures_out"] = deps
            props["departures_in"] = deps
        if props:
            tx.run("MATCH (r:BusRoute {code:$code}) SET r += $props", code=code, props=props).consume()
        if stops is not None:
            if len(stops) < 2:
                raise Invalid("Tuyến cần ít nhất 2 trạm")
            _apply_route_stops(tx, code, stops)

    db.write(work)
    invalidate_graph()
    return get_route(code)


def delete_route(code: str):
    def work(tx):
        if not tx.run("MATCH (r:BusRoute {code:$code}) RETURN r", code=code).single():
            raise NotFound(f"Không tìm thấy tuyến {code}")
        tx.run("MATCH ()-[e:CONNECTS_TO {route:$code}]->() DELETE e", code=code).consume()
        tx.run("MATCH (r:BusRoute {code:$code}) DETACH DELETE r", code=code).consume()

    db.write(work)
    invalidate_graph()


def update_segment(code: str, from_id: str, to_id: str, distance_km: float, time_min: float):
    """Sửa trọng số của một đoạn (áp dụng cho cả hai chiều)."""
    def work(tx):
        res = tx.run(
            """
            MATCH (a:Station)-[e:CONNECTS_TO {route:$code}]-(b:Station)
            WHERE (a.id = $a AND b.id = $b) OR (a.id = $b AND b.id = $a)
            SET e.distance_km = $d, e.time_min = $t
            RETURN count(e) AS n
            """, code=code, a=from_id, b=to_id, d=distance_km, t=time_min).single()
        if not res or res["n"] == 0:
            raise NotFound("Không có đoạn đường này trên tuyến")

    db.write(work)
    invalidate_graph()
    return get_route(code)


# ----------------------------------------------------------------------------- GIỜ XUẤT BẾN
_DIR_PROP = {"out": "departures_out", "in": "departures_in"}


def _mod_departures(code: str, direction: str, fn):
    prop = _DIR_PROP.get(direction)
    if not prop:
        raise Invalid("direction phải là 'out' (lượt đi) hoặc 'in' (lượt về)")

    def work(tx):
        row = tx.run(f"MATCH (r:BusRoute {{code:$code}}) RETURN r.{prop} AS deps", code=code).single()
        if not row:
            raise NotFound(f"Không tìm thấy tuyến {code}")
        new = fn(list(row["deps"] or []))
        tx.run(f"MATCH (r:BusRoute {{code:$code}}) SET r.{prop} = $deps", code=code, deps=new).consume()

    db.write(work)
    return get_route(code)


def add_departure(code: str, direction: str, time: str):
    def fn(deps):
        if time in deps:
            raise Conflict(f"Giờ {time} đã có trong danh sách")
        return sorted(deps + [time])
    return _mod_departures(code, direction, fn)


def remove_departure(code: str, direction: str, time: str):
    def fn(deps):
        if time not in deps:
            raise NotFound(f"Không có giờ {time} trong danh sách")
        return [d for d in deps if d != time]
    return _mod_departures(code, direction, fn)


# ----------------------------------------------------------------------------- ĐỒ THỊ ĐỂ VẼ
def graph_view(route: str | None = None):
    edges = db.read(
        """
        MATCH (r:BusRoute)-[sa:STOPS_AT]->(a:Station)
        MATCH (r)-[sb:STOPS_AT]->(b:Station)
        WHERE sb.seq = sa.seq + 1 AND ($route IS NULL OR r.code = $route)
        MATCH (a)-[e:CONNECTS_TO {route: r.code}]->(b)
        RETURN a.id AS `from`, b.id AS to, r.code AS route, r.color AS color,
               e.distance_km AS distance_km, e.time_min AS time_min
        """,
        route=route or None,
    )
    ids = {e["from"] for e in edges} | {e["to"] for e in edges}
    nodes = [r["s"] for r in db.read("MATCH (s:Station) RETURN s {.*} AS s ORDER BY s.id")
             if not route or r["s"]["id"] in ids]
    return {"nodes": nodes, "edges": edges}
