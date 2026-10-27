"""Demo kiểm thử toàn diện hệ thống Bus Neo4j (Routing Engine + API)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "seed"))

from data import build_dataset
from app.routing import build_graph, find_path, compare
from app import repository
from app.main import app
from fastapi.testclient import TestClient


def main():
    print("=" * 65)
    print("🚌 DEMO KIỂM THỬ HỆ THỐNG TRA CỨU XE BUÝT (BUS-NEO4J)")
    print("=" * 65)

    # 1. Nạp bộ dữ liệu mẫu
    print("\n[BƯỚC 1] Khởi tạo mạng lưới dữ liệu đồ thị mẫu...")
    stations, routes, edges = build_dataset()
    print(f" -> Tổng số trạm (:Station): {len(stations)}")
    print(f" -> Tổng số tuyến (:BusRoute): {len(routes)} (tuyến: {', '.join(r['code'] for r in routes)})")
    print(f" -> Tổng số đoạn nối [:CONNECTS_TO]: {len(edges)}")
    g = build_graph(stations, routes, edges)
    print(" -> Dựng đồ thị trạng thái (State Graph) thành công!")

    # Hàm tiện ích tìm id trạm theo tên
    def find_id(name):
        return next(s["id"] for s in stations if s["name"] == name)

    # 2. Demo Ca 1: Tuyến đi thẳng (Không cần chuyển tuyến)
    orig_name, dest_name = "Chợ Bến Thành", "ĐHQG TP.HCM"
    o_id, d_id = find_id(orig_name), find_id(dest_name)
    print(f"\n[BƯỚC 2] Demo Ca 1: Đi thẳng từ '{orig_name}' đến '{dest_name}'")
    res1 = find_path(g, o_id, d_id, mode="shortest", metric="time", initial_wait=True)
    print(f" -> Tìm thấy đường: {res1['found']}")
    print(f" -> Số lần đổi tuyến: {res1['transfers']}")
    print(f" -> Tuyến phục vụ: Tuyến {res1['legs'][0]['route']} ({res1['legs'][0]['route_name']})")
    print(f" -> Số trạm đi qua: {res1['num_stops']} trạm")
    print(f" -> Thời gian chờ xe đầu: {res1['wait_time_min']} phút | Thời gian ngồi xe: {res1['ride_time_min']} phút")
    print(f" -> Tổng thời gian: {res1['total_time_min']} phút | Quãng đường: {res1['total_distance_km']} km")

    # 3. Demo Ca 2: Chuyển tuyến - So sánh Shortest vs Fewest Transfers
    orig_name2, dest_name2 = "Bến xe Quận 8", "Bến xe An Sương"
    o_id2, d_id2 = find_id(orig_name2), find_id(dest_name2)
    print(f"\n[BƯỚC 3] Demo Ca 2: Chuyển tuyến từ '{orig_name2}' đến '{dest_name2}'")
    comp = compare(g, o_id2, d_id2, metric="time", initial_wait=True)
    sh = comp["shortest"]
    ft = comp["fewest_transfers"]

    print(" ┌── [Phương án nhanh nhất (Shortest)]")
    print(f" │  • Thời gian: {sh['total_time_min']} phút | Quãng đường: {sh['total_distance_km']} km | Đổi tuyến: {sh['transfers']} lần")
    for i, leg in enumerate(sh['legs'], 1):
        print(f" │    + Chặng {i}: Tuyến {leg['route']} từ [{leg['from']['name']}] -> [{leg['to']['name']}] ({leg['num_stops']} trạm, {leg['ride_min']}p)")
    
    print(" ├── [Phương án ít chuyển tuyến nhất (Fewest Transfers)]")
    print(f" │  • Thời gian: {ft['total_time_min']} phút | Quãng đường: {ft['total_distance_km']} km | Đổi tuyến: {ft['transfers']} lần")
    for i, leg in enumerate(ft['legs'], 1):
        print(f" │    + Chặng {i}: Tuyến {leg['route']} từ [{leg['from']['name']}] -> [{leg['to']['name']}] ({leg['num_stops']} trạm, {leg['ride_min']}p)")
    print(" └── Đánh giá: Phương án Shortest nhanh hơn hoặc bằng, phương án Fewest Transfers đổi ít hơn hoặc bằng.")

    # 4. Demo Ca 3: Kiểm thử API FastAPI TestClient
    print("\n[BƯỚC 4] Demo Ca 4: Kiểm thử Endpoint REST API qua TestClient...")
    repository.get_graph = lambda: g
    client = TestClient(app)

    # Test GET /api/path/compare
    r = client.get("/api/path/compare", params={"origin": o_id2, "dest": d_id2, "metric": "time"})
    print(f" -> Gọi GET /api/path/compare: HTTP {r.status_code}")
    assert r.status_code == 200, "Lỗi HTTP status!"
    data = r.json()
    assert "shortest" in data and "fewest_transfers" in data
    print(" -> Dữ liệu JSON trả về đầy đủ 2 phương án so sánh!")

    # Test Validation 422
    r_bad = client.get("/api/path", params={"origin": "S01", "dest": "S02", "mode": "invalid_mode"})
    print(f" -> Gọi GET /api/path với mode không hợp lệ: HTTP {r_bad.status_code} (Bắt lỗi đầu vào thành công)")
    assert r_bad.status_code == 422

    print("\n" + "=" * 65)
    print("✅ TẤT CẢ CÁC BƯỚC DEMO VÀ TEST ĐÃ HOÀN TẤT THÀNH CÔNG RỰC RỠ!")
    print("=" * 65)


if __name__ == "__main__":
    main()

