# Tra cứu lộ trình xe buýt công cộng với Neo4j

Ứng dụng web tìm đường xe buýt giữa hai trạm, hỗ trợ **hành trình nhanh/ngắn nhất** và **hành trình ít lần chuyển tuyến nhất**, có tính **thời gian chờ khi đổi tuyến**. Dữ liệu lưu dưới dạng đồ thị trong **Neo4j**; backend **Python + FastAPI**; giao diện web tiếng Việt.

> **Lưu ý về dữ liệu:** bộ dữ liệu mẫu mô phỏng mạng lưới xe buýt TP. Hồ Chí Minh. Tên trạm/tuyến bám theo địa danh thật, nhưng tọa độ, khoảng cách, thời gian và giờ chạy chỉ là ước lượng phục vụ học tập, **không phải dữ liệu vận hành chính thức**.

## Phân công thực hiện đồ án

| STT | Thành viên | Tài khoản GitHub / Email | Vai trò & Nhiệm vụ chính | Đóng góp |
|:---:|:---|:---|:---|:---:|
| 1 | **LapTruong525** | [`LapTruong525`](https://github.com/LapTruong525) <br> (`laptruong72@gmail.com`) | • Thiết kế mô hình CSDL đồ thị Neo4j & Cypher<br>• Cài đặt lõi thuật toán Dijkstra không gian trạng thái<br>• Tối ưu In-memory Cache & Quản lý Transaction | **50%** |
| 2 | **baohuit23** | [`baohuit23`](https://github.com/baohuit23) <br> (`nguyenbaohuit23@gmail.com`) | • Xây dựng hệ thống REST API FastAPI & Pydantic Validation<br>• Thiết kế giao diện Web tra cứu & tích hợp đồ thị `vis-network`<br>• Viết bộ kiểm thử tự động & Hoàn thiện báo cáo | **50%** |

## 1. Cấu trúc dự án

```
bus-neo4j/
├── backend/app/
│   ├── main.py         API FastAPI (+ phục vụ giao diện web)
│   ├── repository.py   Toàn bộ truy vấn Cypher: CRUD, nạp đồ thị
│   ├── routing.py      Thuật toán Dijkstra có chuyển tuyến (thuần Python)
│   ├── schemas.py      Kiểm tra dữ liệu đầu vào (Pydantic)
│   ├── geo.py          Khoảng cách haversine, ước lượng thời gian, sinh giờ xuất bến
│   ├── db.py           Kết nối Neo4j (Bolt)
│   └── config.py       Đọc cấu hình từ .env
├── seed/
│   ├── data.py         Dữ liệu mẫu: 57 trạm, 10 tuyến, 198 cạnh
│   └── seed.py         Nạp dữ liệu vào Neo4j
├── frontend/           index.html, style.css, app.js
├── cypher/queries.cypher   Truy vấn Cypher để khám phá đồ thị trong Neo4j Browser
├── tests/              Kiểm thử thuật toán và API (không cần Neo4j)
├── requirements.txt
└── .env.example
```

## 2. Mô hình đồ thị

```
(:Station {id, name, district, lat, lon})
(:BusRoute {code, name, headway_min, first_departure, last_departure, color,
            departures_out[], departures_in[]})

(:BusRoute)-[:STOPS_AT {seq}]->(:Station)
(:Station)-[:CONNECTS_TO {route, distance_km, time_min}]->(:Station)
```

- `:Station` là trạm dừng. `:BusRoute` là tuyến xe, lưu giãn cách (`headway_min`) và danh sách giờ xuất bến hai lượt.
- `[:STOPS_AT {seq}]` ghi thứ tự các trạm của tuyến.
- `[:CONNECTS_TO]` là đoạn đường **có hướng** giữa hai trạm liên tiếp, mang thuộc tính `route` (mã tuyến) và hai trọng số `distance_km`, `time_min`. Mỗi đoạn có hai cạnh (đi và về).
- Hai ràng buộc duy nhất được tạo tự động: `Station.id` và `BusRoute.code`.

Đề bài nhắc cả `[:CONNECTS_TO]` lẫn `[:ROUTE_TO]`; dự án dùng thống nhất tên **`CONNECTS_TO`**.

Quy mô dữ liệu mẫu: **57** `:Station`, **10** `:BusRoute` (01, 02, 03, 04, 06, 08, 14, 18, 19, 52), **198** `[:CONNECTS_TO]`.

## 3. Cài đặt và chạy

### 3.1. Chuẩn bị Neo4j Desktop
1. Mở **Neo4j Desktop** → tạo (hoặc mở) một Project → **Add → Local DBMS**, đặt mật khẩu (ví dụ `bus12345`).
2. Bấm **Start** cho DBMS. Cổng Bolt mặc định là `7687`.
3. Chỉ dùng được Neo4j **5.x** (đã dùng cú pháp `CREATE CONSTRAINT ... IF NOT EXISTS FOR ... REQUIRE`). Không cần cài thêm plugin nào.

### 3.2. Cài thư viện Python (cần Python 3.10+)
```bash
cd bus-neo4j
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3.3. Cấu hình kết nối
```bash
cp .env.example .env             # Windows: copy .env.example .env
```
Mở `.env` và điền mật khẩu bạn đã đặt ở bước 3.1.

### 3.4. Nạp dữ liệu mẫu
```bash
python seed/seed.py
```
Kết quả mong đợi: `Xong. Trong Neo4j hiện có: 57 Station, 10 BusRoute, 198 CONNECTS_TO`.
(Thêm `--keep` nếu muốn giữ dữ liệu cũ và chỉ MERGE thêm.)

### 3.5. Chạy ứng dụng
```bash
uvicorn app.main:app --app-dir backend --reload
```
Mở trình duyệt tại **http://127.0.0.1:8000**. Tài liệu API tự sinh tại http://127.0.0.1:8000/docs.

## 4. Chức năng

| Tab | Nội dung |
|---|---|
| **Tìm đường** | Chọn điểm đi/đến, chọn tối ưu theo *thời gian* hoặc *quãng đường*. Hiển thị song song **phương án ngắn nhất** và **phương án ít chuyển tuyến nhất**, từng chặng, thời gian chờ khi đổi tuyến, và lộ trình tô sáng trên đồ thị. |
| **Trạm dừng** | CRUD trạm: tìm kiếm, thêm, sửa (đổi tọa độ sẽ tự tính lại trọng số các cạnh kề), xóa (các tuyến đi qua được nối lại trạm trước với trạm sau). |
| **Tuyến xe** | Thêm/sửa/xóa tuyến; sắp xếp, thêm, bỏ trạm của tuyến; sửa **trọng số** từng đoạn; thêm/xóa **giờ xuất bến** theo lượt đi/lượt về. |
| **Đồ thị mạng lưới** | Vẽ toàn bộ đồ thị theo tọa độ thật, tô màu theo tuyến, lọc theo tuyến, rê chuột để xem trọng số. |

### API chính

| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/path?origin=S01&dest=S20&mode=shortest&metric=time` | Một hành trình. `mode`: `shortest` \| `fewest_transfers`; `metric`: `time` \| `distance`; `initial_wait`: `true/false` |
| GET | `/api/path/compare?origin=…&dest=…` | Cả hai phương án cùng lúc |
| GET/POST | `/api/stations` | Danh sách (có `?q=`) / thêm trạm |
| GET/PUT/DELETE | `/api/stations/{id}` | Xem / sửa / xóa trạm |
| GET/POST | `/api/routes` | Danh sách / thêm tuyến |
| GET/PUT/DELETE | `/api/routes/{code}` | Xem / sửa (kể cả danh sách trạm) / xóa tuyến |
| POST/DELETE | `/api/routes/{code}/departures` | Thêm / xóa giờ xuất bến |
| PUT | `/api/routes/{code}/segments` | Sửa trọng số một đoạn (cả hai chiều) |
| GET | `/api/graph?route=52` | Dữ liệu đồ thị để vẽ |

## 5. Thuật toán tìm đường

Dijkstra chạy trên **đồ thị trạng thái `(trạm, tuyến đang đi)`**, nên việc đổi tuyến trở thành một cạnh có chi phí như mọi cạnh khác:

- **Đi tiếp** trên cùng tuyến sang trạm kế: cộng `time_min` và `distance_km` của cạnh `CONNECTS_TO`.
- **Đổi tuyến** tại một trạm: cộng thời gian chờ **= `headway_min` của tuyến mới / 2** (kỳ vọng chờ khi xe đến đều đặn) và tăng số lần chuyển thêm 1.
- **Lên xe lần đầu**: cộng thời gian chờ = `headway_min` / 2 (có thể tắt bằng `initial_wait=false`).

Mỗi trạng thái mang bộ ba *(thời gian, quãng đường, số lần chuyển)*; thứ tự so sánh từ điển quyết định chế độ:

| Chế độ | Thứ tự ưu tiên |
|---|---|
| `shortest` + `time` | thời gian → số lần chuyển → quãng đường |
| `shortest` + `distance` | quãng đường → thời gian → số lần chuyển |
| `fewest_transfers` + `time` | số lần chuyển → thời gian → quãng đường |

Cả ba thành phần đều không âm và cộng dồn, nên Dijkstra vẫn cho kết quả tối ưu. Đồ thị được nạp từ Neo4j bằng Cypher, giữ trong bộ nhớ và tự làm mới sau mỗi thao tác ghi.

Nếu muốn so sánh, `cypher/queries.cypher` có sẵn truy vấn `shortestPath` thuần Cypher (đường ít trạm nhất, không xét tuyến).

## 6. Kiểm thử

```bash
python -m pytest tests -q
```
13 test kiểm tra: dữ liệu mẫu đạt yêu cầu quy mô; đi thẳng không chuyển tuyến; các chặng nối khớp tại trạm chuyển; *thời gian của phương án ngắn nhất ≤ phương án ít chuyển tuyến* và *số lần chuyển của phương án ít chuyển ≤ phương án ngắn nhất* trên hơn 50 cặp trạm; chế độ quãng đường; bật/tắt thời gian chờ đầu; trạm không liên thông; các điểm cuối API và kiểm tra dữ liệu đầu vào.

Các test này chạy trên đồ thị nạp sẵn trong RAM nên **không cần Neo4j**. Tầng Cypher trong `repository.py` và `seed.py` chỉ chạy được khi có Neo4j; nếu gặp lỗi cú pháp ở môi trường của bạn, hãy gửi thông báo lỗi để chỉnh lại.

## 7. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| Banner đỏ "Chưa kết nối được cơ sở dữ liệu" | Start DBMS trong Neo4j Desktop; kiểm tra `NEO4J_URI`, `NEO4J_PASSWORD` trong `.env` |
| `Authentication failed` | Sai mật khẩu trong `.env` |
| Giao diện trống, `0` trạm | Chưa chạy `python seed/seed.py` |
| Biểu đồ không hiện | Trang cần tải thư viện vis-network từ `unpkg.com`; kiểm tra kết nối Internet |
