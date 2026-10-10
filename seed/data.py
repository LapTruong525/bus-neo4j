"""Dữ liệu mẫu MÔ PHỎNG mạng lưới xe buýt TP. Hồ Chí Minh.

Tên trạm/tuyến bám theo địa danh thật nhưng tọa độ, khoảng cách, thời gian và giờ chạy
chỉ là ước lượng phục vụ học tập, KHÔNG phải dữ liệu vận hành chính thức.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from app.geo import gen_departures, segment_metrics  # noqa: E402

# key: (tên, quận/huyện, vĩ độ, kinh độ)
_STATIONS = {
    # Trung tâm
    "bt": ("Chợ Bến Thành", "Quận 1", 10.7725, 106.6980),
    "cv239": ("Công viên 23/9", "Quận 1", 10.7694, 106.6940),
    "nht": ("Nhà hát Thành phố", "Quận 1", 10.7766, 106.7030),
    "taodan": ("Công viên Tao Đàn", "Quận 1", 10.7749, 106.6925),
    "dlap": ("Dinh Độc Lập", "Quận 1", 10.7770, 106.6954),
    "ductba": ("Nhà thờ Đức Bà", "Quận 1", 10.7798, 106.6990),
    "tcv": ("Thảo Cầm Viên", "Quận 1", 10.7876, 106.7053),
    "bachdang": ("Bến Bạch Đằng", "Quận 1", 10.7733, 106.7062),
    "phudong": ("Ngã sáu Phù Đổng", "Quận 1", 10.7655, 106.6900),
    "tandinh": ("Chợ Tân Định", "Quận 1", 10.7897, 106.6917),
    "conrua": ("Hồ Con Rùa", "Quận 3", 10.7826, 106.6962),
    "dancho": ("Vòng xoay Dân Chủ", "Quận 3", 10.7787, 106.6800),
    # Quận 4, 5, 6, 8, 10
    "vandon": ("Bến Vân Đồn", "Quận 4", 10.7600, 106.7055),
    "dhsg": ("Đại học Sài Gòn", "Quận 5", 10.7603, 106.6821),
    "khtn": ("ĐH Khoa học Tự nhiên", "Quận 5", 10.7629, 106.6822),
    "cho_ran": ("Bệnh viện Chợ Rẫy", "Quận 5", 10.7573, 106.6597),
    "vanlang": ("Công viên Văn Lang", "Quận 5", 10.7545, 106.6623),
    "ancong": ("Chợ An Đông", "Quận 5", 10.7530, 106.6720),
    "kimbien": ("Chợ Kim Biên", "Quận 5", 10.7502, 106.6585),
    "binhtay": ("Chợ Bình Tây", "Quận 6", 10.7506, 106.6504),
    "bxcl": ("Bến xe Chợ Lớn", "Quận 6", 10.7503, 106.6440),
    "phulam": ("Vòng xoay Phú Lâm", "Quận 6", 10.7459, 106.6329),
    "binhphu": ("Ngã tư Bình Phú", "Quận 6", 10.7452, 106.6270),
    "bxmt": ("Bến xe Miền Tây", "Bình Tân", 10.7405, 106.6195),
    "ngabay": ("Ngã bảy Lý Thái Tổ", "Quận 10", 10.7668, 106.6709),
    "lethiriengpark": ("Công viên Lê Thị Riêng", "Quận 10", 10.7829, 106.6637),
    "chuy": ("Cầu Chữ Y", "Quận 8", 10.7428, 106.6990),
    "xomcui": ("Chợ Xóm Củi", "Quận 8", 10.7375, 106.6830),
    "bxq8": ("Bến xe Quận 8", "Quận 8", 10.7396, 106.6660),
    # Tân Bình, Phú Nhuận, Gò Vấp, Quận 12, Hóc Môn
    "hoangvanthu": ("Công viên Hoàng Văn Thụ", "Tân Bình", 10.7964, 106.6627),
    "bayhien": ("Ngã tư Bảy Hiền", "Tân Bình", 10.7935, 106.6532),
    "chotanbinh": ("Chợ Tân Bình", "Tân Bình", 10.7926, 106.6445),
    "baqueo": ("Ngã ba Bà Quẹo", "Tân Bình", 10.7950, 106.6330),
    "phunhuan": ("Ngã tư Phú Nhuận", "Phú Nhuận", 10.7990, 106.6800),
    "giadinh": ("Công viên Gia Định", "Phú Nhuận", 10.8115, 106.6781),
    "ngatuga": ("Ngã tư Ga", "Quận 12", 10.8435, 106.6830),
    "thanhloc": ("Thạnh Lộc", "Quận 12", 10.8625, 106.6830),
    "quangtrung": ("Công viên Phần mềm Quang Trung", "Quận 12", 10.8523, 106.6286),
    "bxansuong": ("Bến xe An Sương", "Hóc Môn", 10.8410, 106.6070),
    # Bình Thạnh và TP. Thủ Đức (hướng Xa lộ Hà Nội)
    "cauthinghe": ("Cầu Thị Nghè", "Bình Thạnh", 10.7920, 106.7080),
    "hangxanh": ("Ngã tư Hàng Xanh", "Bình Thạnh", 10.8015, 106.7110),
    "bxmd": ("Bến xe Miền Đông", "Bình Thạnh", 10.8143, 106.7106),
    "binhtrieu": ("Ngã tư Bình Triệu", "TP. Thủ Đức", 10.8330, 106.7230),
    "hiepbinh": ("Ngã tư Hiệp Bình", "TP. Thủ Đức", 10.8470, 106.7300),
    "thuduc_cho": ("Chợ Thủ Đức", "TP. Thủ Đức", 10.8493, 106.7531),
    "linhtrung": ("KCX Linh Trung", "TP. Thủ Đức", 10.8700, 106.7780),
    "nonglam": ("ĐH Nông Lâm", "TP. Thủ Đức", 10.8710, 106.7920),
    "cau_saigon": ("Cầu Sài Gòn", "TP. Thủ Đức", 10.7985, 106.7285),
    "thaodien": ("Ga Metro Thảo Điền", "TP. Thủ Đức", 10.8023, 106.7392),
    "anphu": ("Ga Metro An Phú", "TP. Thủ Đức", 10.7992, 106.7518),
    "rachchiec": ("Ga Metro Rạch Chiếc", "TP. Thủ Đức", 10.8052, 106.7630),
    "phuoclong": ("Ga Metro Phước Long", "TP. Thủ Đức", 10.8135, 106.7690),
    "binhthai": ("Ga Metro Bình Thái", "TP. Thủ Đức", 10.8260, 106.7740),
    "thuduc_ga": ("Ga Metro Thủ Đức", "TP. Thủ Đức", 10.8520, 106.7730),
    "khcn": ("Ga Metro Khu Công nghệ cao", "TP. Thủ Đức", 10.8530, 106.7980),
    "suoitien": ("Khu du lịch Suối Tiên", "TP. Thủ Đức", 10.8660, 106.8030),
    "dhqg": ("ĐHQG TP.HCM", "TP. Thủ Đức", 10.8754, 106.8000),
}

# (mã tuyến, tên, headway phút, giờ đầu, giờ cuối, màu, [các trạm theo thứ tự])
_ROUTES = [
    ("01", "Bến Thành – Bến xe Chợ Lớn", 12, "05:00", "20:30", "#e6194b",
     ["bt", "cv239", "phudong", "dhsg", "ancong", "vanlang", "kimbien", "binhtay", "bxcl"]),
    ("02", "Bến Thành – Bến xe Miền Tây", 10, "05:00", "21:00", "#3cb44b",
     ["bt", "phudong", "khtn", "dhsg", "cho_ran", "binhtay", "bxcl", "phulam", "binhphu", "bxmt"]),
    ("03", "Bến Thành – Thạnh Lộc", 15, "05:15", "20:30", "#4363d8",
     ["bt", "dlap", "ductba", "conrua", "tandinh", "dancho", "phunhuan", "giadinh", "ngatuga", "thanhloc"]),
    ("04", "Bến Thành – Bến xe An Sương", 10, "04:45", "21:30", "#f58231",
     ["bt", "taodan", "conrua", "lethiriengpark", "hoangvanthu", "bayhien", "chotanbinh", "baqueo", "bxansuong"]),
    ("06", "Bến xe Chợ Lớn – ĐH Nông Lâm", 15, "05:00", "20:00", "#911eb4",
     ["bxcl", "binhtay", "cho_ran", "ngabay", "lethiriengpark", "dancho", "phunhuan", "hangxanh",
      "bxmd", "binhtrieu", "hiepbinh", "thuduc_cho", "nonglam"]),
    ("08", "Bến xe Quận 8 – ĐHQG TP.HCM", 12, "05:00", "20:30", "#008080",
     ["bxq8", "xomcui", "chuy", "vandon", "bachdang", "bt", "nht", "cauthinghe", "hangxanh",
      "cau_saigon", "anphu", "phuoclong", "thuduc_ga", "suoitien", "dhqg"]),
    ("14", "Bến xe Miền Đông – Bến xe Miền Tây", 20, "05:30", "19:30", "#9a6324",
     ["bxmd", "hangxanh", "dancho", "lethiriengpark", "ngabay", "cho_ran", "phulam", "binhphu", "bxmt"]),
    ("18", "Bến xe An Sương – ĐHQG TP.HCM", 15, "05:00", "20:00", "#808000",
     ["bxansuong", "quangtrung", "ngatuga", "binhtrieu", "hiepbinh", "thuduc_cho", "linhtrung", "dhqg"]),
    ("19", "Bến Thành – KCX Linh Trung – ĐHQG", 12, "05:00", "21:00", "#f032e6",
     ["bt", "nht", "tcv", "cauthinghe", "hangxanh", "bxmd", "binhtrieu", "hiepbinh", "thuduc_cho",
      "linhtrung", "dhqg"]),
    ("52", "Bến Thành – ĐHQG TP.HCM", 8, "04:30", "21:30", "#e6a100",
     ["bt", "nht", "tcv", "cauthinghe", "hangxanh", "cau_saigon", "thaodien", "anphu", "rachchiec",
      "phuoclong", "binhthai", "thuduc_ga", "khcn", "suoitien", "dhqg"]),
]

def build_dataset():
    """Trả về (stations, routes, edges) sẵn sàng nạp vào Neo4j."""
    key_to_id = {k: f"S{i:02d}" for i, k in enumerate(_STATIONS, start=1)}
    stations = [
        {"id": key_to_id[k], "name": v[0], "district": v[1], "lat": v[2], "lon": v[3]}
        for k, v in _STATIONS.items()
    ]
    by_id = {s["id"]: s for s in stations}

    routes, edges = [], []
    for code, name, headway, first, last, color, keys in _ROUTES:
        stops = [key_to_id[k] for k in keys]
        deps = gen_departures(first, last, headway)
        routes.append({
            "code": code, "name": name, "headway_min": headway,
            "first_departure": first, "last_departure": last, "color": color,
            "departures_out": deps, "departures_in": deps, "stops": stops,
        })
        for a, b in zip(stops, stops[1:]):
            sa, sb = by_id[a], by_id[b]
            dist, mins = segment_metrics(sa["lat"], sa["lon"], sb["lat"], sb["lon"])
            edges.append({"from": a, "to": b, "route": code, "distance_km": dist, "time_min": mins})
            edges.append({"from": b, "to": a, "route": code, "distance_km": dist, "time_min": mins})
    return stations, routes, edges


if __name__ == "__main__":
    s, r, e = build_dataset()
    print(f"{len(s)} trạm, {len(r)} tuyến, {len(e)} cạnh CONNECTS_TO")
