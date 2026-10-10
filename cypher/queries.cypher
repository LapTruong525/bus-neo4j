// Các truy vấn Cypher hữu ích để khám phá đồ thị trong Neo4j Browser

// 1) Xem toàn bộ mạng lưới (trạm + cạnh)
MATCH p = (:Station)-[:CONNECTS_TO]->(:Station) RETURN p LIMIT 300;

// 2) Các tuyến đi qua một trạm và thứ tự trạm đó trong tuyến
MATCH (r:BusRoute)-[st:STOPS_AT]->(s:Station {name: 'Chợ Bến Thành'})
RETURN r.code AS tuyen, r.name AS ten_tuyen, st.seq AS thu_tu ORDER BY tuyen;

// 3) Các trạm chuyển tuyến tốt nhất (nhiều tuyến cùng đi qua)
MATCH (r:BusRoute)-[:STOPS_AT]->(s:Station)
WITH s, collect(r.code) AS tuyen
WHERE size(tuyen) >= 3
RETURN s.name AS tram, size(tuyen) AS so_tuyen, tuyen ORDER BY so_tuyen DESC;

// 4) Danh sách trạm của một tuyến theo thứ tự
MATCH (:BusRoute {code: '52'})-[st:STOPS_AT]->(s:Station)
RETURN st.seq AS stt, s.name AS tram ORDER BY stt;

// 5) Đường đi ÍT TRẠM nhất giữa hai trạm (không xét tuyến) bằng shortestPath của Cypher
MATCH (a:Station {name: 'Bến xe Quận 8'}), (b:Station {name: 'Bến xe An Sương'}),
      p = shortestPath((a)-[:CONNECTS_TO*..60]->(b))
RETURN [n IN nodes(p) | n.name] AS hanh_trinh, length(p) AS so_chang;

// 6) Đường đi NHANH nhất theo trọng số bằng Cypher thuần (liệt kê rồi sắp xếp; chỉ hợp với đồ thị nhỏ/giới hạn độ sâu)
MATCH (a:Station {name: 'Chợ Bến Thành'}), (b:Station {name: 'Ga Metro An Phú'}),
      p = (a)-[:CONNECTS_TO*..14]->(b)
WHERE all(r IN relationships(p) WHERE r.route = relationships(p)[0].route)
RETURN [n IN nodes(p) | n.name] AS hanh_trinh,
       reduce(t = 0.0, r IN relationships(p) | t + r.time_min) AS phut,
       reduce(d = 0.0, r IN relationships(p) | d + r.distance_km) AS km
ORDER BY phut LIMIT 1;

// 7) Kiểm tra số lượng dữ liệu theo yêu cầu đề bài
MATCH (s:Station) WITH count(s) AS tram
MATCH (r:BusRoute) WITH tram, count(r) AS tuyen
MATCH ()-[e:CONNECTS_TO]->() RETURN tram, tuyen, count(e) AS canh;

// 8) Tìm các trạm "mồ côi" (không thuộc tuyến nào)
MATCH (s:Station) WHERE NOT (s)-[:CONNECTS_TO]-() RETURN s.id, s.name;
