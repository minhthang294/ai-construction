# POC: DeepSeek V4.1 Flash đọc trang scan một lần

Ngày: 11/11/2026. Model: `opencode-go/deepseek-v4.1-flash` (chỉ dùng model này). Đây là POC trích xuất một lần để làm giàu kho tri thức, **không ghi vào `data/app.db`** và không thay thế OCR baseline.

## Phạm vi

- 6 trang từ 2 PDF scan thật: bìa báo cáo, 3 trang bản vẽ, 2 trang thuyết minh.
- Mỗi trang render 220 DPI, chạy OCR Tesseract `vie+eng` để làm baseline.
- Gửi ảnh trang cho DeepSeek V4.1 Flash, yêu cầu JSON theo schema cố định.
- So sánh hai chế độ:
  - **agent**: `opencode run --file`, model được dùng tool đọc/crop ảnh.
  - **direct**: gửi ảnh trực tiếp qua OpenCode session API, không qua tool loop.

## Kết quả tổng hợp

### Chế độ agent (tool/crop)

| Trang | Loại | JSON | Key values | Warning | Model conf | OCR conf | Thời gian | Input / output token |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bìa báo cáo | other | OK | 4 | 4 | 0,82 | 69,2 | 23,9 s | 8.371 / 1.070 |
| Bản vẽ p6 | drawing | OK | 19 | 6 | 0,75 | 64,7 | **636,0 s** | 51.210 / 6.493 |
| Bản vẽ p10 | drawing | OK | 16 | 6 | 0,78 | 83,2 | 38,5 s | 1.075 / 1.716 |
| Bản vẽ p20 | drawing | OK | 7 | 7 | 0,60 | 67,9 | 40,2 s | 5.299 / 1.144 |
| Thuyết minh p5 | text | OK | 0 | 4 | 0,90 | 68,3 | 32,5 s | 7.995 / 1.381 |
| Thuyết minh p10 | specification | OK | 23 | 4 | 0,88 | 95,1 | 38,8 s | 8.382 / 2.021 |

Tổng thời gian: **~13,5 phút** cho 6 trang. Một trang bản vẽ phức tạp chiếm 10,6 phút và 1,3 triệu token cache read do model dùng nhiều tool/crop.

Độ ổn định của agent mode kém: chạy lại trang bản vẽ p10 cho kết quả **443 s** và 11 key values, so với 38,5 s và 16 key values ở lần trước. Vì vậy không nên dùng agent mode cho batch 241 trang.

### Chế độ direct image API

| Trang | Loại | JSON | Key values | Warning | Model conf | OCR conf | Thời gian | Input / output token |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bản vẽ p6 | drawing | OK | 3 | 4 | 0,72 | 64,7 | 113,5 s | 5.363 / 737 |
| Bản vẽ p10 | drawing | OK | 22 | 7 | 0,76 | 83,2 | 55,7 s | 10.097 / 2.025 |
| Bản vẽ p20 | drawing | OK | 5 | 4 | 0,72 | 67,9 | 112,4 s | 5.361 / 857 |
| Thuyết minh p5 | other | OK | 0 | 4 | 0,88 | 68,3 | 28,1 s | 8.460 / 1.462 |
| Thuyết minh p10 | text | OK | 17 | 5 | 0,85 | 95,1 | 61,4 s | 8.332 / 1.862 |

Tổng thời gian: **~6,2 phút** cho 5 trang. Không có tool loop, ít token cache hơn.

## POC 20 trang (tile + direct)

Chạy 10 trang bản vẽ bằng tile 2×2 + title block, 240 DPI, 4 worker; 10 trang thuyết minh bằng direct, 220 DPI. Không ghi DB, không dùng model khác.

| Nhóm | Trang | JSON OK | Key values | KV/trang | Trang có conflict | Numeric warning | Conf trung bình | Tổng thời gian |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bản vẽ | 10 | 10/10 | 594 | 59,4 | 6/10 (58 conflict) | 112 | 0,589 | 23,8 phút |
| Thuyết minh | 10 | 10/10 | 75 | 7,5 | 0/10 | 0 | 0,901 | 5,4 phút |
| **Tổng** | **20** | **20/20** | **669** | — | **6/10** | **112** | — | **~29,2 phút** |

Token bản vẽ: 292.230 input / 72.823 output / 131.448 reasoning / 349.440 cache read. Token thuyết minh: 41.677 / 11.464 / 18.958 / 59.520. Chi phí ước tính theo bảng giá DeepSeek: **~0,10 USD cho 20 trang**, tức khoảng **1,2–1,4 USD cho 241 trang**.

Nhận xét:
- Tile mode tăng recall rõ rệt trên bản vẽ: có trang 71–78 key values, gồm kích thước, cao độ, ghi chú, bảng.
- Conflict được phát hiện đúng: 6/10 trang bản vẽ có mâu thuẫn; trang p6 có 30 conflict và 73 warning.
- 112 numeric warning trên bản vẽ cho thấy số của model thường không khớp OCR — một phần do OCR bản vẽ kém, một phần do model đọc sai. Không thể tự động coi là đúng.
- Trang thuyết minh sạch hơn nhiều: 0 conflict, 0 numeric warning, confidence 0,84–0,96.
- Trang mục lục có 0 key values là bình thường.
- 20/20 JSON hợp lệ; merge giữ metadata full page và lọc warning nhiễu của tile.

Ước tính full 241 trang: tuần tự ~6,3 giờ; chạy 4 worker ~1,5–2 giờ; chi phí ~1,3 USD. Chưa nên chạy full vì tỷ lệ conflict trên bản vẽ còn cao.

Review sheet: `/tmp/opencode/poc20-review.html` (ảnh + JSON + warning từng trang).

## Chất lượng

### Điểm tốt

- **11/11 lượt trả JSON hợp lệ** theo schema.
- Xác định đúng loại trang, tiêu đề, số hiệu bản vẽ, revision khi có.
- Trích được bảng, ghi chú, kích thước, cao độ, đơn vị.
- Tự sinh warning khi khung tên bị che, chữ mờ, ô revision trống.
- Citation dạng `quote` là chuỗi nhìn thấy trên trang, có thể dùng để đối chiếu.
- Với trang thuyết minh chữ rõ, kết quả rất tốt: số hợp đồng, kích thước cầu, sức chịu tải, v.v.

### Rủi ro đã thấy

- **Sai số:** cùng trang bản vẽ p6, chế độ agent đọc tổng chiều dài `87140`, chế độ direct đọc `87440`. OCR không bắt được con số này. Không có nguồn nào trong POC xác nhận chắc chắn.
- **Sai đơn vị:** một lượt ghi `mm` cho chuỗi kích thước dù ghi chú trang là `cm`.
- **Mất chi tiết:** direct mode đọc trang bản vẽ phức tạp chỉ được 3 key values, trong khi agent mode đọc 19. Ảnh bị server downscale hoặc chi tiết quá nhỏ.
- **Tên riêng/ký hiệu:** có lúc đọc `DAP` thành `ĐẠP`, `CMB` thành `OMB`.
- **Chữ ký, dấu đỏ, ô revision trống:** model thường để `null` và warning, đúng hướng, nhưng không đọc được.
- **Confidence của model không phải xác suất đúng**; không thể dùng trực tiếp làm ngưỡng tự động.
- **Không nên dùng số liệu model làm kết luận kỹ thuật** nếu chưa mở trang gốc.

## Chi phí ước tính

Theo bảng giá DeepSeek Flash hiện tại, 6 trang chế độ agent ước tính **~0,025 USD**; 5 trang direct **~0,010 USD**. Con số này rất nhỏ so với thời gian công sức, nhưng cần đo lại khi chạy toàn bộ.

## Kết luận

1. **Direct image API** là hướng chính cho trang text/thuyết minh: nhanh, rẻ, JSON tốt, 0 conflict trên 10 trang mẫu.
2. **Tile 2×2 + title block** là hướng chính cho bản vẽ: recall cao hơn hẳn full-page, nhưng conflict cần được xử lý trước khi dùng.
3. **Không bỏ OCR**: OCR là baseline để đối chiếu số liệu, tạo text search và citation.
4. **Không dùng kết quả model làm số liệu cuối cùng**: mọi kích thước/khối lượng phải kiểm tra trang gốc.
5. **Chưa nên chạy full 241 trang** ngay. Cần thêm bước phân loại verified/proposed và kiểm chứng 20–30 trang nữa trước khi chạy toàn bộ.

## Đề xuất bước tiếp theo

- Phân loại key values thành:
  - `verified`: số/đơn vị khớp OCR hoặc không có conflict;
  - `proposed`: có conflict, warning số/đơn vị, hoặc confidence thấp.
- Chỉ `verified` được đưa vào KB dạng tin cậy; `proposed` vào hàng đợi kỹ sư duyệt.
- Thêm vote/consensus giữa full page và các tile cho các giá trị trùng tên; nếu lệch, giữ cả hai và đánh dấu conflict.
- Chạy thêm 20–30 trang bản vẽ có nhiều dạng khác nhau để đo tỷ lệ conflict thực tế.
- Nếu tỷ lệ conflict giảm sau khi lọc, mới chạy full 241 trang với 4 worker, lưu `page_sha256`, model/prompt version và review queue.

## Artifacts

- Script: `scripts/deepseek_page_extract.py` (`--mode direct|agent`, `--tile-grid`)
- Logic tile/merge/validate: `backend/app/engineering_ai/page_extraction.py`
- Review sheet: `scripts/poc_review.py` → `/tmp/opencode/poc20-review.html`
- Kết quả 20 trang: `/tmp/opencode/poc20-drawings`, `/tmp/opencode/poc20-report`
- Kết quả POC nhỏ: `/tmp/opencode/deepseek-poc-*`
- Không có dữ liệu thật nào được ghi vào DB hay commit vào repo.
