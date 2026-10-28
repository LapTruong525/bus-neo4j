"""Nạp dữ liệu mẫu vào Neo4j.

Chạy từ thư mục gốc dự án:
    python seed/seed.py            # xóa dữ liệu bus cũ rồi nạp lại
    python seed/seed.py --keep     # không xóa, chỉ MERGE thêm
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import db, repository  # noqa: E402
from data import build_dataset  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="giữ dữ liệu cũ, chỉ MERGE thêm")
    args = ap.parse_args()

    stations, routes, edges = build_dataset()
    print(f"Chuẩn bị nạp: {len(stations)} trạm, {len(routes)} tuyến, {len(edges)} cạnh CONNECTS_TO")

    try:
        db.verify()
    except Exception as exc:
        sys.exit(f"Không kết nối được Neo4j ({exc}).\n"
                 "Hãy Start DBMS trong Neo4j Desktop và kiểm tra NEO4J_URI/NEO4J_PASSWORD trong .env")

    repository.ensure_schema()

    def work(tx):
        if not args.keep:
            tx.run("MATCH (n) WHERE n:Station OR n:BusRoute DETACH DELETE n").consume()
        tx.run(
            """
            UNWIND $rows AS s
            MERGE (n:Station {id: s.id})
            SET n.name = s.name, n.district = s.district, n.lat = s.lat, n.lon = s.lon
            """, rows=stations).consume()
        tx.run(
            """
            UNWIND $rows AS r
            MERGE (b:BusRoute {code: r.code})
            SET b.name = r.name, b.headway_min = r.headway_min,
                b.first_departure = r.first_departure, b.last_departure = r.last_departure,
                b.color = r.color, b.departures_out = r.departures_out, b.departures_in = r.departures_in
            """, rows=routes).consume()
        # (:BusRoute)-[:STOPS_AT {seq}]->(:Station)
        stops = [{"code": r["code"], "id": sid, "seq": i}
                 for r in routes for i, sid in enumerate(r["stops"])]
        tx.run(
            """
            UNWIND $rows AS x
            MATCH (b:BusRoute {code: x.code}), (s:Station {id: x.id})
            MERGE (b)-[st:STOPS_AT]->(s) SET st.seq = x.seq
            """, rows=stops).consume()
        # (:Station)-[:CONNECTS_TO {route, distance_km, time_min}]->(:Station)
        tx.run(
            """
            UNWIND $rows AS e
            MATCH (a:Station {id: e.from}), (b:Station {id: e.to})
            MERGE (a)-[c:CONNECTS_TO {route: e.route}]->(b)
            SET c.distance_km = e.distance_km, c.time_min = e.time_min
            """, rows=edges).consume()

    db.write(work)
    s = repository.stats()
    print(f"Xong. Trong Neo4j hiện có: {s['stations']} Station, {s['routes']} BusRoute, "
          f"{s['edges']} CONNECTS_TO")
    db.close_driver()


if __name__ == "__main__":
    main()
