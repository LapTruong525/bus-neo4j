"""Tiện ích địa lý: tính khoảng cách/thời gian giữa hai trạm và sinh giờ xuất bến."""
import math

ROAD_FACTOR = 1.3     # đường thực tế dài hơn đường chim bay
AVG_SPEED_KMH = 18.0  # tốc độ trung bình xe buýt nội đô
DWELL_MIN = 0.7       # thời gian dừng đón/trả khách mỗi trạm


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def segment_metrics(lat1, lon1, lat2, lon2):
    """Trả về (khoảng cách km, thời gian phút) giữa hai trạm liên tiếp."""
    dist = max(round(haversine_km(lat1, lon1, lat2, lon2) * ROAD_FACTOR, 2), 0.1)
    minutes = max(round(dist / AVG_SPEED_KMH * 60 + DWELL_MIN, 1), 1.0)
    return dist, minutes


def gen_departures(first: str, last: str, headway: int):
    """Sinh danh sách giờ xuất bến từ giờ đầu đến giờ cuối theo headway (phút)."""
    h, m = map(int, first.split(":"))
    h2, m2 = map(int, last.split(":"))
    cur, end = h * 60 + m, h2 * 60 + m2
    out = []
    while cur <= end:
        out.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += max(int(headway), 1)
    return out
