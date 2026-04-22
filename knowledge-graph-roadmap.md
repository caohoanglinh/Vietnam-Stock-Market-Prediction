# Knowledge Graph — Stock Market Context Layer

> **Mục tiêu:** Không dự đoán giá (đã có XGBoost/RF/LSTM), mà cung cấp context giúp user hiểu *tại sao* giá có thể tăng/giảm thông qua mối quan hệ giữa 100 mã cổ phiếu và tin tức thị trường.

---

## Bước 1 — Xác định mục tiêu

Hệ thống phục vụ **2 loại tín hiệu song song**:

| Nguồn | Loại thông tin |
|---|---|
| Model dự đoán (XGBoost/RF/LSTM) | Dự đoán tăng/giảm sau 1/5/10 ngày dựa trên 20 ngày gần nhất |
| Knowledge Graph | Context: tại sao, lan truyền từ đâu, mâu thuẫn hay đồng thuận |

Graph không ra lệnh mua/bán — nó **hiển thị xung đột và chuỗi nhân quả** để user tự đánh giá.

---

## Bước 2 — Công nghệ

Dùng **Property Graph** với `networkx` (prototype) — không cần server, đủ cho 100 mã.

Nếu sau này cần query phức tạp hoặc production: migrate sang **Neo4j**.

---

## Bước 3 — Mô hình dữ liệu

### Node types

| Node | Attributes |
|---|---|
| `Stock` | ticker, sector, subsector, exchange |
| `Article` | url, source, published_at, raw_text |
| `Event` | type, sentiment, confidence, date |
| `Sector` | name, macro_drivers[] |

### Edge types

| Edge | Từ → Đến | Attributes |
|---|---|---|
| `COMPETE_DIRECT` | Stock → Stock | weight |
| `COMPETE_INDIRECT` | Stock → Stock | weight |
| `SECTOR_PEER` | Stock → Stock | weight |
| `UPSTREAM_OF` | Stock → Stock | — |
| `DOWNSTREAM_OF` | Stock → Stock | — |
| `MENTIONS` | Article → Stock | sentiment, confidence |
| `TRIGGERS` | Article → Event | impact_score |
| `AFFECTS` | Event → Stock | direction, confidence |

---

## Bước 4 — Chuẩn bị dữ liệu

### Structured (đã có)
- 100 mã cổ phiếu + sector/subsector map
- Relationship map đầy đủ: `compete_direct`, `sector_peers`, `upstream`, `downstream`, `note` cho từng mã
- OHLCV 20 ngày + 16 features từ vnstock

### Unstructured (cần làm)
- Crawl news: CafeF, Vietstock, VnEconomy, HOSE announcements
- Filter: chỉ giữ bài mention mã cổ phiếu hoặc tên công ty
- NLP: entity extraction + sentiment + news_type

---

## Bước 5 — Nạp dữ liệu

### Giai đoạn 1 — Static graph (làm ngay)

Load toàn bộ `stock_relationships.py` vào networkx graph cho cả 100 mã.

```python
# Load nodes
for ticker, sector in SECTOR_MAP.items():
    G.add_node(ticker, sector=sector)

# Load edges
for ticker, rel in STOCK_RELATIONSHIPS.items():
    for target in rel["compete_direct"]:
        G.add_edge(ticker, target, type="COMPETE_DIRECT")
    for target in rel["sector_peers"]:
        G.add_edge(ticker, target, type="SECTOR_PEER")
    for target in rel["downstream"]:
        G.add_edge(ticker, target, type="DOWNSTREAM_OF")
    for target in rel["upstream"]:
        G.add_edge(ticker, target, type="UPSTREAM_OF")
```

### Giai đoạn 2 — Dynamic layer (sau khi có news pipeline)

Mỗi ngày crawl news → parse → thêm `Article` node + `Event` node + edge `AFFECTS` với confidence score.

---

## Bước 6 — Logic xử lý tín hiệu

### 6.1 — Phân loại news_type

| news_type | Ý nghĩa | Ví dụ |
|---|---|---|
| `macro` | Ảnh hưởng toàn ngành | SBV cắt lãi suất, giá dầu tăng |
| `company` | Nội tại 1 công ty | VCB báo lãi, NVL vỡ trái phiếu |

### 6.2 — Impact direction

| Relationship | macro | company + negative | company + positive |
|---|---|---|---|
| `sector_peer` | same ↑↑ | same ↓↓ (trust) | neutral |
| `compete_direct` | same ↑↑ | opposite ↑ (thị phần) | opposite ↓ |
| `downstream` | same | same | same |
| `upstream` | same | same | same |

### 6.3 — Conflict resolution

Khi graph signal và news signal mâu thuẫn nhau:

```
news_confidence >> graph_confidence  →  tin news, ghi nhận graph là rủi ro tiềm ẩn
graph_confidence >> news_confidence  →  tin graph, coi news là short-term noise
|news_conf - graph_conf| < threshold →  CONFLICT — hiển thị cả 2 cho user
```

Output khi conflict:
```
⚠️  VIB — Tín hiệu mâu thuẫn
├── 📉 Graph:  VCB đang tăng trưởng mạnh → VIB có thể chịu áp lực cạnh tranh
└── 📈 News:   VIB vừa công bố lợi nhuận Q3 tăng 40% YoY
```

Conflict **không phải lỗi hệ thống** — đây là tín hiệu có giá trị, cho thấy mã đang có câu chuyện riêng bất chấp áp lực ngành.

---

## Bước 7 — Kiểm thử

Các query phải pass trước khi dùng thật:

```
Q1: VCB tin xấu macro   → BID, CTG, MBB, TCB... (sector_peers) bị kéo xuống cùng
Q2: VCB tin xấu company → BID, CTG (compete_direct) hưởng lợi
Q3: VHM chậm tiến độ    → CTD, HBC, HPG, HT1 mất đơn hàng
Q4: GAS tăng giá        → DPM, DCM, POW, NT2 tăng chi phí
Q5: BID graph=down, news=up → CONFLICT verdict + hiển thị cả 2 lý do
```

---

## Bước 8 — Duy trì & mở rộng

### Daily job

```
08:00  Crawl news đêm qua
06:30  NLP pipeline → thêm Article/Event node vào graph
07:00  Tính conflict signals cho 100 mã
07:30  Dashboard sẵn sàng trước giờ mở cửa (09:00)
```

### Mở rộng về sau

```
→ Thêm macro nodes: lãi suất SBV, tỷ giá USD/VND, giá dầu, Baltic Dry Index
→ Edge mới: HPG ──[SENSITIVE_TO]──► GiaDau
→ Tích hợp model prediction vào tooltip của mỗi node trên graph
```

---

## Thứ tự thực hiện

| Tuần | Việc cần làm |
|---|---|
| 1 | Load `stock_relationships.py` → networkx graph → visualize pyvis (100 mã) |
| 2 | Crawl news pipeline: CafeF + Vietstock |
| 3 | NLP: entity extraction + sentiment + phân loại macro/company |
| 4 | Ghép news vào graph + conflict detection logic |
| 5 | Dashboard: graph visualization + conflict alerts + model prediction tooltip |

---

## Quan hệ với hệ thống hiện tại

```
vnstock API
    │
    ├──► OHLCV data ──► 16 features ──► XGBoost / RF / LSTM ──► Predict 1/5/10 ngày
    │
    └──► Metadata ──► Stock nodes
                          │
News crawler ────────────► Article nodes ──► NLP ──► Event nodes
                          │
stock_relationships.py ──► Edges (static)
                          │
                          ▼
                    Knowledge Graph
                          │
                          ▼
                    Dashboard (graph + conflict + prediction tooltip)
```