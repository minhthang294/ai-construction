# Chẩn đoán RAG Engineering AI — Giai đoạn A (chỉ đọc)

Ngày: 2026-11-12  
Phạm vi: `backend/app/engineering_ai/`, `frontend/src/features/engineering-ai/`, bản sao DB tại `/tmp`  
Trạng thái: **chẩn đoán, chưa sửa pipeline, chưa commit**

Tài liệu tham chiếu:

- `docs/2026-11-12-agent-execution.md`
- `docs/2026-11-12-download-rag-plan.md`
- `docs/AGENT_BOUNDARIES.md`

## 0. Kết luận điều hành

1. Câu hỏi gốc **“Cầu chính phân đoạn 1 các cọc nào hỏng?”** có dữ kiện trên ảnh gốc, nhưng có **hai bảng cùng thỏa điều kiện**, tương ứng hai nhóm sửa chữa khác nhau:
   - **Nhóm 2 — trang bản vẽ 8** (sheet `TK-02`): **45 cọc**.
   - **Nhóm 3 — trang bản vẽ 15** (sheet `TK-09`): **39 cọc**.
   - Hai danh sách **không trùng nhau**; hợp là **84 cọc**. Câu hỏi không nêu “nhóm” nên hệ thống phải nêu cả hai hoặc hỏi lại nhóm, **không được tự chọn một**.
2. Retrieval hiện tại **không trả được danh sách cọc**. Top-1 của câu gốc là chunk tiêu đề 32 ký tự của trang 8 (`PHÁN ĐOẠN 1 - CAU CHÍNH - NHÓM 2`), không chứa tên cọc. Trang 15 nằm ngoài top-5 (hạng 6), các chunk chứa bảng xếp hạng 65 trở xuống. **Answer-bearing Recall@5 = 0**.
3. Ca cọc **H77** có đủ dữ kiện trực tiếp trên trang 22 (sheet `TK-16`): chiều sâu đục `t = 1 cm`, chiều dài sửa `L1 = 0,2 m`, thể tích đục `0,003 m³`, diện tích quét keo `0,304 m²`, diện tích mài phẳng `1,280 m²`. Nhưng retrieval top-5 **không chứa trang 22**; mã `H77` **không xuất hiện trong bất kỳ chunk nào** của index hiện tại. Đây là lỗi trích xuất/OCR + index, không chỉ là lỗi retrieval.
4. Ca dầm **I-30-31** có dữ kiện kích thước trên trang 46 (sheet `TK-40`): vùng hư hỏng `L1 = 1500 mm`, chiều dài sửa/dán `L = 1900 mm`, chiều sâu đục `T5 cm` ở sườn và `T7 cm` ở đáy, diện tích dán sợi thủy tinh `4,560 m²`. **Không có dòng khối lượng đục, diện tích quét keo, diện tích mài phẳng riêng** trên trang này; chưa có quy tắc bóc tách được duyệt nên hệ thống phải từ chối các số đó, chỉ trả kích thước và diện tích dán sợi.
5. Index hiện tại dùng **`local-hash-v1:256`** cho toàn bộ 5.105 chunk. Đây là hash từ khóa, không phải semantic embedding. DB chỉ có đúng một model vector này.
6. Chưa xác minh được **chat provider thực tế** của tiến trình đang chạy: không đọc được `/proc/1918/environ` (không đủ quyền), shell hiện tại không có biến `ENGINEERING_AI_*`. Theo code, mặc định là `ExtractiveProvider` nếu không cấu hình. Không in khóa/URL.

## 1. Phương pháp và phạm vi đọc

### 1.1 Bản sao DB, chỉ đọc

- DB gốc: `data/app.db` — **không sửa**.
- Bản sao chẩn đoán: `/tmp/opencode/rag-diag/app-copy.db` và `/tmp/opencode/rag-diag/retrieval-copy.db`.
- Truy vấn metadata bằng `sqlite3` chế độ `mode=ro`; đo retrieval bằng Python trên bản sao, không ghi DB dùng chung.
- Không sửa PDF nguồn, không sửa `data/app.db`, không sửa code sản phẩm.

### 1.2 Trạng thái kho hồ sơ tại thời điểm đo

| Hồ sơ | ID | Trang | Chunk | `status` | `is_effective` |
| --- | --- | ---: | ---: | --- | --- |
| `bản vẽ scan_1.pdf` | `a8144e78-7dc7-485a-a6ee-7a5781faa71a` | 133 | 4.078 | `ready` | 1 |
| `Tập 1 - thuyết minh báo cáo KTKT sửa chữa nứt cọc dầm cầu cảng_0001.pdf` | `708a4a11-58a4-411c-bf94-f43fa5564b4a` | 108 | 1.027 | `ready` | 1 |

Tổng: **2 hồ sơ ready/effective, 241 trang, 5.105 chunk**.

### 1.3 Provider thực tế

- `embeddings_from_env()` trả về `local-hash-v1:256`, dimension 256.
- Bảng `engineering_ai_document_embeddings` chỉ có một model: `local-hash-v1:256`, 5.105 vector.
- Đây là bằng chứng trực tiếp rằng index đã được tạo bằng hash từ khóa, không phải embedding đa ngữ.
- Chat provider: không xác minh được từ tiến trình đang chạy do không đủ quyền đọc môi trường. Trong shell chẩn đoán không có biến `ENGINEERING_AI_*`. Theo `providers.py`, nếu không đặt `ENGINEERING_AI_PROVIDER` thì mặc định là `ExtractiveProvider`.
- Không in API key, token, URL hoặc bất kỳ giá trị bí mật nào.

## 2. Câu hỏi gốc: đối chiếu ảnh bản vẽ gốc

### 2.1 Câu hỏi và các cách viết đã đo

Câu chuẩn:

> Cầu chính phân đoạn 1 các cọc nào hỏng?

Các cách viết tương đương đã đo:

1. `Cầu chính phân đoạn I các cọc nào hư hỏng?`
2. `Đoạn 1 cầu chính cọc hư hỏng`
3. `Cọc hư hỏng cầu chính phân đoạn 1`
4. `Cầu chính phân đoạn 1 cọc nào nứt?`
5. `Cầu chính phân đoạn 1 các cọc nào hỏng?` (bản không dấu)
6. `Các cọc hỏng ở cầu chính phân đoạn 1 là cọc nào?`
7. `Liệt kê cọc hư hỏng phân đoạn 1 cầu chính nhóm 3`
8. `Cầu chính phân đoạn 1 nhóm 2 cọc nào hỏng?`

### 2.2 Bằng chứng trên ảnh gốc

#### A. Trang bản vẽ 8 — Nhóm 2 (sheet `TK-02`)

- Tiêu đề trên bản vẽ: **`PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 2`**.
- Tên bản vẽ: `MẶT BẰNG NHÓM CỌC - NHÓM 2 (1/7)`.
- Vùng bảng: bảng bên phải, các cột:
  - `Phân loại`
  - `Phân đoạn`
  - `Tên cọc (KS)`
  - `Chiều dài vết nứt L (m)`
- Các dòng có `Phân đoạn = Phân đoạn 1`: từ **`I3`** đến **`D151`**, tổng **45 dòng**.
- Đây là danh sách cọc hư hỏng kèm chiều dài vết nứt, không phải danh sách cọc sửa chữa chung.

Danh sách đầy đủ (trích từ ảnh, không lấy từ OCR):

`I3, I4, H2, G2, F3, F4, H5, F7, G8, F10, F12, G11, G14, H14, I16, F19, F22, I24, I25, F27, G29, G32, F33, F34, F36, G35, G38, F39, F40, G41, F42, F43, F45, H47, H48, A2, A5, A8, E146, C146, D147, D148, A148, D150, D151`

#### B. Trang bản vẽ 15 — Nhóm 3 (sheet `TK-09`)

- Tiêu đề trên bản vẽ: **`PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 3`** (nửa trên); nửa dưới là `PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 3`.
- Tên bản vẽ: `MẶT BẰNG NHÓM CỌC - NHÓM 3 (1/6)`.
- Vùng bảng: bảng bên phải, cùng cấu trúc cột như trang 8.
- Các dòng có `Phân đoạn = Phân đoạn 1`: từ **`I6`** đến **`A150`**, tổng **39 dòng**.
- Ranh giới phân đoạn: ô gộp `Phân đoạn 1` kết thúc sau dòng `A150`; đường kẻ ngang của ô gộp nằm ngay trên dòng `I49`. Vì vậy `I49` là dòng đầu của `Phân đoạn 2`, không thuộc phân đoạn 1.
- Ghi chú hiệu chỉnh: bản nháp trước xếp `I49` vào phân đoạn 1; đối chiếu lại đường kẻ của ô gộp xác nhận `I49` thuộc phân đoạn 2. Danh sách nhóm 3 phân đoạn 1 vì vậy còn **39 cọc**, không phải 40.

Danh sách đầy đủ (trích từ ảnh, không lấy từ OCR):

`I6, I7, I10, I12, I19, I22, I27, I28, I30, I31, I36, I37, I46, H26, H32, G28, F6, F28, F30, F31, F37, F48, E2, E8, E11, E145, E147, C5, C8, C11, C14, B147, B148, B149, B150, A11, A14, A147, A150`

#### C. Các trang liên quan nhưng không trả lời trực tiếp

- **Trang 6** (sheet `TMB-01`): `MẶT BẰNG TỔNG THỂ CẦU CẢNG`; các nhãn `PHÂN ĐOẠN 1 (CẦU DẪN)`, `PHÂN ĐOẠN 2 (CẦU DẪN)`, ... Đây là phân đoạn của **cầu dẫn**, không phải “cầu chính”. Trang này là distractor mạnh trong retrieval (top-2 của câu gốc).
- **Trang 7** (sheet `TK-01`): `PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 1`; bảng chỉ có `H77`, `F66`, `I90`. Nhóm 1 **không có phân đoạn 1** trên bản vẽ này.
- **Trang 31** (sheet `TK-25`): `BẢNG THỐNG KÊ CỌC HƯ HỎNG NHÓM III`; có các nhóm III.1–III.8, cột `Vị trí` (Cầu chính/Cầu dẫn), nhưng **không có cột `Phân đoạn`**. Không dùng trang này thay cho trang 15 để trả lời “phân đoạn 1”.

### 2.3 Đáp án trực tiếp

Vì câu hỏi không nêu nhóm, có hai đáp án đúng khác nhau:

| Cách hiểu | Trang | Số cọc | Danh sách |
| --- | ---: | ---: | --- |
| Cầu chính, phân đoạn 1, **nhóm 2** | 8 (`TK-02`) | 45 | `I3 ... D151` |
| Cầu chính, phân đoạn 1, **nhóm 3** | 15 (`TK-09`) | 39 | `I6 ... A150` |
| **Hợp hai nhóm** | 8 + 15 | **84** | 45 + 39, không trùng |

Không có cọc nào thuộc cả hai danh sách. Vì vậy:

- Nếu người hỏi chỉ muốn một nhóm, phải hỏi lại: “nhóm 2 hay nhóm 3?”.
- Nếu người hỏi muốn toàn bộ cầu chính phân đoạn 1, trả **84 cọc** và nêu rõ hai nhóm.
- Không được trả lời bằng danh sách của trang 31 hoặc bằng đoạn thuyết minh chung về cọc nứt.

### 2.4 Vì sao câu hỏi này khó với RAG hiện tại

1. **Hai nguồn cùng thỏa** nhưng không có trường “nhóm” trong câu hỏi.
2. **Trang 8 và 15 là bảng scan OCR**, không phải bảng có cấu trúc. Text OCR bị cắt thành nhiều chunk nhỏ 5–243 ký tự; tên cọc nằm rải rác, không gắn với dòng/cột.
3. **Tiêu đề trang 15 bị OCR sai**: `PHAN ĐOẠN 1 - CAEl'.slmCHiNH - NHÓM 3` — mất chữ “CẦU CHÍNH”, nên truy vấn có “cầu chính” không khớp tiêu đề này.
4. **Trang 6 có “PHÂN ĐOẠN 1 (CẦU DẪN)”** — trùng từ “phân đoạn 1” nhưng sai đối tượng (cầu dẫn). Nó được xếp top-2.
5. **Chunk tiêu đề ngắn** được BM25 ưu tiên hơn chunk bảng dài; top-1 chỉ là tiêu đề 32 ký tự.

## 3. Ca cọc H77

### 3.1 Định vị cấu kiện

- H77 thuộc **Nhóm I**, **Cầu chính**, **Phân đoạn 2** — không thuộc phân đoạn 1.
- Bằng chứng:
  - Trang 7 (`TK-01`), bảng `PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 1`: dòng `H77`, chiều dài vết nứt `0,2 m`.
  - Trang 22 (`TK-16`), `BẢNG THỐNG KÊ CỌC HƯ HỎNG NHÓM I`: dòng `Loại 1 | Cầu chính | H77 | 1 | 0,2 | 1`.
- Vì vậy nếu người dùng hỏi “H77 có thuộc phân đoạn 1 không?”, đáp án là **không**; H77 thuộc phân đoạn 2, nhóm 1.

### 3.2 Thông số trực tiếp trên trang 22

Bảng `BẢNG KHỐI LƯỢNG NHÓM I`, cột `Khối lượng 1 cọc` → `L1 = 0,2m` → `Cầu chính` → `t = 1cm`:

| Hạng mục | Giá trị | Đơn vị | Nguồn |
| --- | ---: | --- | --- |
| Đục bê tông om vỡ dày T1 cm | **0,003** | m³ | Trang 22, bảng khối lượng, dòng 1, cột L1=0,2m/Cầu chính/t=1cm |
| Tẩy gỉ cốt thép | 0,015 | m² | Trang 22, dòng 2 |
| Vệ sinh bề mặt cọc sau khi đục | 0,304 | m² | Trang 22, dòng 3 |
| Mài tạo phẳng và vệ sinh bề mặt cọc (phạm vi dán sợi) | **1,280** | m² | Trang 22, dòng 4 |
| Quét keo epoxy HM-180C3P (0,6 kg/m²) | **0,304** | m² | Trang 22, dòng 6 |
| Rắc cát tạo nhám bề mặt | 0,304 | m² | Trang 22, dòng 7 |
| Trám và đầu cọc bằng vữa trám dày trung bình 5cm | 0,108 | m² | Trang 22, dòng 8 |
| Vữa không co ngót tính năng cao | 0,003 | m³ | Trang 22, dòng 11 |
| Sợi carbon dày 1mm dán ướt — T1 | 1,120 | m² | Trang 22, dòng 12 |
| Sợi carbon dày 1mm dán ướt — T2 | 0,850 | m² | Trang 22, dòng 12 |
| Sợi carbon dày 1mm dán ướt — T3 | 0,640 | m² | Trang 22, dòng 12 |
| Hệ sơn bảo vệ bề mặt | 1,280 | m² | Trang 22, dòng 13 |
| Vận chuyển đổ thải | 0,003 | m³ | Trang 22, dòng 14 |
| Bao tải (0,064 m³/bao) | 1,000 | bao | Trang 22, dòng 15 |

Tóm tắt trả lời cho H77:

- **Chiều sâu đục**: `t = 1 cm`.
- **Chiều dài sửa**: `L1 = 0,2 m`.
- **Thể tích đục**: `0,003 m³/cọc`.
- **Diện tích quét keo**: `0,304 m²/cọc`.
- **Diện tích mài phẳng**: `1,280 m²/cọc` (phạm vi dán sợi).
- Đây là **số liệu hồ sơ ghi sẵn**, không phải hệ thống tự tính.

### 3.3 Quy trình sửa chữa

Nguồn: thuyết minh **trang PDF 32** (trang in `-28-`), mục `4.2. Công tác sửa chữa cọc`, đoạn `Cọc nhóm 1`; chi tiết hình học trên **trang bản vẽ 21** (`SỬA CHỮA CỌC HƯ HỎNG NHÓM I (1/2)`).

Thứ tự công tác:

1. Đục bỏ bê tông om vỡ, tẩy gỉ cốt thép, vệ sinh bề mặt bê tông thân cọc sau khi đục.
2. Quét keo epoxy dính bám HM-180C3P (hoặc tương đương) trên bề mặt bê tông ẩm ướt.
3. Phun cát trong phạm vi quét keo để tạo nhám.
4. Lắp dựng ván khuôn; bơm vữa tự chảy không co ngót cường độ cao Sumen Grout 60 (hoặc tương đương).
5. Mài phẳng bề mặt; dán 02 lớp sợi carbon dày 1 mm (sau tẩm keo) xung quanh chu vi cọc.
6. Sơn bảo vệ bề mặt sợi carbon: 02 lớp, lớp lót epoxy 2 thành phần + lớp phủ kháng hóa chất/chống UV.

Lưu ý: trang 21 là bản vẽ chi tiết gia cường composite; trang 22 là bảng thống kê/khối lượng nhóm I. Cần đối chiếu cả hai để tránh nhầm “Loại 1” với “Nhóm 1” nếu quy ước hồ sơ thay đổi.

### 3.4 Trạng thái dữ kiện

| Dữ kiện | Có trên hồ sơ? | Loại |
| --- | --- | --- |
| Mã cọc H77 | Có | Trực tiếp |
| Nhóm I / phân đoạn 2 / cầu chính | Có | Trực tiếp |
| Chiều sâu đục 1 cm | Có | Trực tiếp |
| Chiều dài sửa 0,2 m | Có | Trực tiếp |
| Thể tích đục 0,003 m³ | Có | Trực tiếp (bảng khối lượng 1 cọc) |
| Diện tích quét keo 0,304 m² | Có | Trực tiếp |
| Diện tích mài phẳng 1,280 m² | Có | Trực tiếp |
| Quy trình | Có | Chỉ dẫn kỹ thuật chung, áp dụng cho cọc nhóm 1 |

## 4. Ca dầm I-30-31

### 4.1 Định vị cấu kiện

- Trang bản vẽ **46** (sheet `TK-40`):
  - `SỬA CHỮA HƯ HỎNG DẦM I-30-31 (1/1)`
  - `HIỆN TRẠNG VÀ GIẢI PHÁP SỬA CHỮA DẦM NHÓM I - CẦU CHÍNH (10/56)`
- Đây là dầm nhóm I, cầu chính.

### 4.2 Kích thước và khối lượng trực tiếp

Trên trang 46:

- `Phạm vi xử lý hư hỏng L1 = 1500` (mm) — chiều dài vùng hư hỏng.
- `Lxl = L = 1900` (mm) — chiều dài sửa/dán.
- Mặt cắt:
  - `Om vỡ BT sườn dầm dày T5 cm` — chiều sâu đục sườn 5 cm.
  - `Om vỡ bê tông đáy dầm dày T7 cm` — chiều sâu đục đáy 7 cm.
- Bảng `BẢNG TỔNG HỢP KHỐI LƯỢNG DÁN SỢI THỦY TINH DẦM I-30-31`:

| Tấm | Kích thước | Số tấm | Diện tích 1 tấm (m²) | Tổng (m²) |
| --- | --- | ---: | ---: | ---: |
| T1 | 1.900 × 0,200 m | 4 | 0,380 | 1,520 |
| T2 | 1.600 × 0,250 m | 7 | 0,400 | 2,800 |
| T3 | 1.600 × 0,150 m | 1 | 0,240 | 0,240 |
| **Tổng** |  |  |  | **4,560** |

### 4.3 Quy trình sửa chữa

Nguồn: thuyết minh **trang PDF 33** (trang in `-29-`), mục `4.3. Công tác sửa chữa dầm ngang, dầm dọc`, đoạn `Dầm cầu chính nhóm 1`.

Thứ tự công tác:

1. Đục tẩy bê tông hư hỏng theo phạm vi hồ sơ thiết kế.
2. Vệ sinh bề mặt, tẩy gỉ cốt thép; nếu mất tiết diện thép, mở rộng đáy dầm để chiều dài hàn nối tối thiểu 30 cm.
3. Quét keo epoxy dính bám HM-180C3P (hoặc tương đương); phun cát trong phạm vi quét keo để tạo nhám.
4. Lắp ván khuôn; bơm vữa tự chảy không co ngót Sumen Grout 60 (hoặc tương đương).
5. Mài phẳng bề mặt đáy dầm; dán 02 lớp sợi thủy tinh dày 0,635 mm:
   - lớp 1 dán dọc dầm;
   - lớp 2 dán vuông góc phương dọc dầm, phủ lên sườn 500 mm cho dầm ngang và 400 mm cho dầm dọc.
6. Quét keo epoxy bảo vệ bề mặt bê tông sườn dầm.
7. Sơn bảo vệ sợi thủy tinh: 02 lớp, lót epoxy + phủ kháng hóa chất/chống UV.

### 4.4 Các số chưa có / phải từ chối

Trang 46 **không** ghi trực tiếp:

- Thể tích bê tông đục (`m³`).
- Diện tích quét keo epoxy (`m²`) — bảng chỉ có diện tích dán sợi thủy tinh.
- Diện tích mài phẳng (`m²`) — không có dòng riêng.

Không được tự nhân `L × b × t` vì:

- Bề rộng vùng đục thay đổi theo mặt cắt và vị trí sườn/đáy.
- Chưa có quy tắc chọn `b` và xử lý chồng lấn giữa các tấm T1/T2/T3.
- Diện tích quét keo có thể khác diện tích dán sợi do mép dán/overlap.

Vì vậy, với câu hỏi “thể tích đục / diện tích quét keo / mài phẳng của dầm I-30-31”, đáp án đúng là **nêu dữ kiện thiếu và không đưa số**. Có thể trả các số đã có: `L1 = 1500 mm`, `L = 1900 mm`, `T5/T7 cm`, diện tích dán sợi `4,560 m²`.

## 5. Đo retrieval top-5

### 5.1 Thiết lập đo

- Top-k = 5.
- Scope = `effective`.
- Chỉ hồ sơ `ready` + `is_effective`.
- Provider index: `local-hash-v1:256`.
- Corpus: 2 hồ sơ, 241 trang, 5.105 chunk.
- Script đo: `/tmp/opencode/rag-diag/measure_retrieval.py`; output: `/tmp/opencode/rag-diag/retrieval-output.txt`.
- Không gọi chat provider; chỉ gọi `search_chunks()` trên bản sao DB.

### 5.2 Bảng top-5

Ghi chú cột `Ứng viên`: `lexical/FTS/KNN` — số chunk có ít nhất một token trùng / số chunk FTS / số láng giềng vector. Tất cả query đều có 5.105 chunk đủ điều kiện.

| Mã | Câu hỏi | Top-5 trang (điểm) | Trang kỳ vọng | Ứng viên | Kết luận |
| --- | --- | --- | --- | --- | --- |
| G1 | Cầu chính phân đoạn 1 các cọc nào hỏng? | 8 (22,4051); 6 (20,0397); 8 (19,2452); 38 (18,4781); 12 (17,8420) | 8, 15 | 2768/2759/20 | Trúng trang 8 nhưng chỉ chunk tiêu đề; trang 15 hạng 6; không có bảng |
| G2 | Cầu chính phân đoạn I các cọc nào hư hỏng? | 8 (19,5879); 8 (18,7266); 6 (18,2092); 37 (18,0714); 12 (17,0129) | 8, 15 | 2345/2332/20 | “I” không khớp “1”; trang 15 ngoài top-5 |
| G3 | Đoạn 1 cầu chính cọc hư hỏng | 93 (20,4597); 8 (17,9469); 37 (16,6733); 22 (16,6247); 35 (16,1664) | 8, 15 | 2539/2505/20 | Top-1 sai (dầm nhóm II); trang 15 ngoài top-5 |
| G4 | Cọc hư hỏng cầu chính phân đoạn 1 | 8 (22,4051); 37 (20,4242); 6 (20,0397); 93 (19,6993); 8 (19,1906) | 8, 15 | 2778/2769/20 | Trúng trang 8; trang 15 ngoài top-5 |
| G5 | Cầu chính phân đoạn 1 cọc nào nứt? | 8 (22,4051); 6 (20,0397); 8 (19,2010); 12 (18,7768); 38 (18,4781) | 8, 15 | 2686/2677/20 | Trúng trang 8; trang 15 ngoài top-5 |
| G6 | Cầu chính phân đoạn 1 các cọc nào hỏng? (không dấu) | 8 (22,3053); 6 (19,9552); 8 (19,1450); 38 (18,8812); 12 (17,7704) | 8, 15 | 2796/2764/20 | Trúng trang 8; trang 15 ngoài top-5 |
| G7 | Các cọc hỏng ở cầu chính phân đoạn 1 là cọc nào? | 8 (21,8554); 6 (19,7966); 8 (18,9637); 38 (18,1490); 97 (17,7770) | 8, 15 | 2958/2951/20 | Trúng trang 8; trang 15 ngoài top-5 |
| G8 | Liệt kê cọc hư hỏng phân đoạn 1 cầu chính nhóm 3 | 8 (26,6270); 8 (26,6193); 20 (23,5678); 20 (23,4800); 93 (23,4752) | 15 | 3079/3074/20 | **Sai nhóm**: trả trang 8 (nhóm 2); trang 15 hạng 11 (22,6814) |
| G9 | Cầu chính phân đoạn 1 nhóm 2 cọc nào hỏng? | 8 (29,8941); 8 (26,7959); 11 (22,9523); 12 (22,8856); 9 (22,8744) | 8 | 3132/3124/20 | Trúng trang 8 nhưng chỉ chunk tiêu đề; không có bảng |
| P1 | Cọc H77 đục sâu bao nhiêu, chiều dài sửa chữa, khối lượng đục, diện tích quét keo, mài phẳng? | 26 (27,7585); 16 (27,7085); 26 (27,4369); 16 (27,2008); 16 (26,5114) | 22 | 1847/1770/20 | **Không trúng trang 22** (hạng 63/74); mã H77 không có trong index |
| B1 | Dầm I-30-31 chiều sâu đục, chiều dài sửa, thể tích đục, diện tích quét keo, mài phẳng? | 16 (22,9055); 46 (22,6796); 26 (22,6509); 16 (21,8974); 26 (21,8932) | 46 | 2248/2180/20 | Trúng trang 46 hạng 2 nhưng chỉ chunk tiêu đề/kích thước; bảng sợi hạng 39 |

### 5.3 Recall@5

| Ca | Page Recall@5 | Answer-bearing Recall@5 | Ghi chú |
| --- | ---: | ---: | --- |
| G1, kỳ vọng cả 8 và 15 | **0,50** (1/2) | **0** | Trang 8 có nhưng chỉ tiêu đề; trang 15 hạng 6 |
| G1, nếu chỉ kỳ vọng trang 8 | 1,00 (1/1) | **0** | Không có chunk bảng trong top-5 |
| G8, kỳ vọng trang 15 | **0** | **0** | Trang 15 hạng 11; top-1/2 là trang 8 nhóm 2 |
| P1, kỳ vọng trang 22 | **0** | **0** | Trang 22 hạng 63/74; H77 không có trong chunk |
| B1, kỳ vọng trang 46 | 1,00 (hạng 2) | **0** cho thể tích/quét keo/mài phẳng | Chỉ có tiêu đề/kích thước; bảng sợi hạng 39 |

**Answer-bearing Recall@5** ở đây nghĩa là top-5 có chunk chứa đúng dòng/bảng trả lời, không chỉ đúng số trang.

### 5.4 Chi tiết lỗi retrieval

#### G1 — câu gốc

- Top-1: chunk `7b512fea`, trang 8, section `PHÁN ĐOẠN 1 - CAU CHÍNH - NHÓM 2`, dài **32 ký tự**, chỉ là tiêu đề.
- Top-3: chunk `c6c5e296`, cùng trang 8, section `PHÁN DOAN 3 - CAU CHÍNH - NHÓM 2` — trả sai phân đoạn.
- Top-2: trang 6, `PHAN ĐOẠN 1 (CẦU DẪN)` — sai đối tượng (cầu dẫn).
- Trang 15: chunk tiêu đề `0c30f820` hạng **6** (17,7721); chunk bảng hạng **65+**.
- Trang 8: các chunk chứa tên cọc nằm ở `chunk_index` 4–18, không chunk nào vào top-5. Chunk 3 chỉ có tiêu đề; chunk 4–5 là text bảng bị cắt vụn.
- Kết quả: extractive answer sẽ quote tiêu đề, không thể liệt kê 45 cọc.

#### G8 — “nhóm 3”

- Top-1 và top-2 đều là trang 8 (nhóm 2), điểm 26,6270 và 26,6193.
- Trang 15 hạng **11** (22,6814), do tiêu đề OCR `CAEl'.slmCHiNH` không khớp “cầu chính”; các chunk bảng trang 15 bị cắt vụn và nhiễu.
- Đây là lỗi **trích xuất/OCR** dẫn đến **index/retrieval** sai, không phải chỉ do embedding.

#### P1 — H77

- Trang 22 không vào top-5; các chunk trang 22 hạng 63 và 74.
- Truy vấn `H77` không khớp chunk nào: **không có chunk nào trong index chứa chuỗi `H77`**. Bảng thống kê trang 22 bị OCR sai/không lưu mã cọc; bảng khối lượng bị cắt thành nhiều chunk, giá trị `0,003` nằm ở chunk 11–12 nhưng không gắn với H77.
- Top-5 toàn trang 16/26 — bảng tổng hợp chung toàn công trình, không phải H77. Nếu answer provider trả lời từ các trang này, nó sẽ đưa số liệu chung hoặc quy trình chung, không phải H77.

#### B1 — I-30-31

- Trang 46 hạng 2, chunk `baa5d375`, section `MẶT BẰNG ĐẨY DAM I-30-31...`; chunk này có tiêu đề và `L1=1500`, nhưng không có bảng sợi.
- Bảng sợi `BẢNG TỔNG HỢP KHỐI LƯỢNG DÁN SỢI THỦY TINH DẦM I-30-31` nằm ở chunk `87771a37`, hạng **39** (17,1716).
- Top-1 là trang 16 (bảng tổng hợp chung), top-3/5 là trang 26 — dễ dẫn đến câu trả lời chung, không gắn I-30-31.

## 6. Phân loại lỗi

| Lớp lỗi | Bằng chứng | Mức độ |
| --- | --- | --- |
| **Trích xuất / OCR** | Trang 15 tiêu đề `CAEl'.slmCHiNH`; bảng trang 8/15 bị cắt thành chunk 5–243 ký tự; trang 22 không có `H77` trong text; bảng trang 22/46 bị dồn cột | Cao |
| **Gắn mã cấu kiện** | Không có trường `pile_code`/`beam_code`; `H77` không có trong chunk; `I-30-31` chỉ xuất hiện trong tiêu đề, không gắn với dòng khối lượng | Cao |
| **Index / chunking** | Chunk theo ký tự/section, không theo hàng bảng; tiêu đề ngắn đứng top-1; bảng khối lượng bị chia nhỏ; không có metadata `table_id`, `row`, `column` | Cao |
| **Retrieval** | `search_chunks()` yêu cầu trùng token hoặc FTS; vector hash không semantic; trang 15 hạng 6/11; trang 22 hạng 63/74; trang 46 bảng sợi hạng 39 | Cao |
| **Answer / citation** | Extractive provider quote top-1 title; không có cơ chế “bảng thiếu dòng thì từ chối”; citation chỉ page-level, không cell-level | Cao |
| **Provider** | Index `local-hash-v1:256`; chat provider chưa xác minh; mặc định extractive nếu không cấu hình | Trung bình |

### 6.1 Cơ chế lỗi cụ thể trong code

- `retrieval.search_chunks()`:
  - chỉ nhận chunk có `matched` token hoặc `fts_ids`; vector đơn thuần không tạo evidence;
  - BM25 cộng điểm mạnh cho chunk ngắn/tiêu đề;
  - không có boost theo `drawing_number`/`page_type`/`table`;
  - không có tìm kiếm exact theo mã cấu kiện.
- `chunking.chunk_text_with_sections()`:
  - cắt theo độ dài/ký tự, không giữ hàng bảng;
  - section chỉ là dòng tiêu đề gần nhất, không phải `table/row`.
- `extraction`/OCR:
  - bảng scan bị OCR rời rạc; không lưu `tables_json` có cấu trúc cho các trang bảng khối lượng;
  - không có bước xác minh `quote` với ảnh trang trước khi index.
- `service.ask()`:
  - nếu có bất kỳ kết quả nào, gọi provider/extractive và trả citation;
  - không kiểm tra “kết quả có chứa đúng mã cấu kiện / đúng dòng bảng không”;
  - không từ chối khi top-1 chỉ là tiêu đề.

## 7. Baseline đề xuất và giá trị đo được

### 7.1 Chỉ số

| Chỉ số | Định nghĩa | Giá trị hiện tại |
| --- | --- | --- |
| Page Recall@5 | Top-5 có đúng trang nguồn | G1 = 0,50 nếu kỳ vọng {8,15}; G8 = 0; P1 = 0; B1 = 1,00 |
| Answer-bearing Recall@5 | Top-5 có chunk chứa đúng dòng/bảng | G1 = 0; G8 = 0; P1 = 0; B1 = 0 cho thể tích/quét keo/mài phẳng |
| Tỷ lệ trả lời đúng có citation | Câu trả lời chứa đúng giá trị + citation đúng trang/ô | Chưa đo end-to-end; dự kiến 0/3 ca chính |
| Tỷ lệ từ chối đúng | Khi thiếu dữ kiện, trả “không đủ chứng cứ” | Chưa đo; code hiện không từ chối nếu có top-5 |
| Độ trễ retrieval | Thời gian `search_chunks()` | Chưa đo chính thức; chạy local, không gọi mạng |
| Chi phí | Provider chat/embedding | Chưa đo; index local hash, không có chi phí embedding ngoài |

### 7.2 Bộ ca tối thiểu cho giai đoạn B

1. **G1**: câu gốc — kỳ vọng nêu hai nhóm hoặc hỏi lại; nếu trả một nhóm phải nêu rõ nhóm.
2. **G8**: “nhóm 3” — kỳ vọng trang 15, 39 cọc (từ `I6` đến `A150`; `I49` là phân đoạn 2).
3. **G9**: “nhóm 2” — kỳ vọng trang 8, 45 cọc.
4. **P1**: H77 — kỳ vọng đúng 5 số: `t=1cm`, `L1=0,2m`, `V=0,003m³`, `keo=0,304m²`, `mài=1,280m²`; nêu H77 thuộc nhóm I phân đoạn 2.
5. **B1**: I-30-31 — kỳ vọng `L1=1500mm`, `L=1900mm`, `T5/T7cm`, diện tích sợi `4,560m²`; **từ chối** thể tích đục/quét keo/mài phẳng vì thiếu dữ kiện.
6. **Câu hỏi “cọc này” không có mã**: phải hỏi lại mã hoặc dùng mã đang chọn trong UI; không tự chọn cọc.
7. **Câu hỏi ngoài dự án**: phải từ chối, không lấy hồ sơ dự án khác.

## 8. Đề xuất giai đoạn B (ưu tiên)

### P0 — Dữ kiện cấu kiện có cấu trúc

1. Thêm lớp `ComponentFact`/`ComponentQuantity` gắn:
   - `project_id`, `document_id`, `page_number`, `table_id`, `row_index`, `column_key`;
   - `component_type` (pile/beam), `component_code` (H77, I-30-31), `group` (1/2/3), `segment`, `location` (cầu chính/cầu dẫn);
   - `value`, `unit`, `source_type` (hồ sơ ghi sẵn / hệ thống tính), `revision`, `verified_status`.
2. Trích bảng có cấu trúc từ PDF/ảnh:
   - ưu tiên PyMuPDF table extraction nếu PDF có text;
   - với trang scan, dùng OCR + vision tile, lưu `table_json` và `cell_bbox`;
   - xác minh thủ công các trang 8, 15, 22, 46 trước khi đánh dấu `verified`.
3. Không đưa `key_values` AI thành sự thật đã duyệt; giữ `proposed/verified`.

### P1 — Index và retrieval

1. Chunk theo bảng/hàng, không cắt tiêu đề thành chunk riêng đứng top-1.
2. Thêm exact search theo mã cấu kiện (`H77`, `I-30-31`) và filter `group/segment/location`.
3. Bỏ điều kiện trùng từ tuyệt đối cho ứng viên vector; nhưng chỉ nhận citation khi quote được xác minh trên trang.
4. Rerank theo:
   - đúng `component_code`;
   - đúng `segment`/`group`;
   - page type `drawing`/`quantity_table`;
   - chunk chứa bảng > chunk tiêu đề.
5. Giữ FTS cho mã bản vẽ, kích thước, số hiệu.

### P2 — Answer và citation

1. Answer chỉ dùng context đã qua `verified` cho số liệu; nếu thiếu dòng/cột thì trả `NO_SOURCE_ANSWER` kèm lý do.
2. Citation phải có `page + table + row + column + quote`; UI mở đúng trang/vùng.
3. Tách “giá trị hồ sơ ghi sẵn” và “giá trị hệ thống tính”; hiển thị công thức ký hiệu, số thay vào, đơn vị.
4. Không chia khối lượng tổng BOQ cho từng cọc/dầm nếu không có quy tắc phân bổ.

### P3 — Test và baseline

1. Tạo golden set với đáp án trang/ô cho G1, G8, G9, P1, B1.
2. Đo lại Page Recall@5 và Answer-bearing Recall@5 trên bản sao DB.
3. Thêm test:
   - “cọc này” không có mã → hỏi lại;
   - câu hỏi cọc/dầm ngoài dự án → từ chối;
   - thiếu chiều sâu/chiều rộng → không trả thể tích;
   - “nhóm 2” vs “nhóm 3” → đúng trang.

## 9. Câu hỏi chưa trả lời / cần Codex chốt

1. **Nhóm nào là đáp án chuẩn cho “Cầu chính phân đoạn 1”?** Cần người kiểm tra chốt nhóm 2, nhóm 3, hay cả hai. Đây là quyết định sản phẩm, không phải lỗi kỹ thuật.
2. **Chat provider thực tế** đang chạy là gì? Không đọc được môi trường tiến trình; cần Codex kiểm tra từ trong service/container và xác nhận `ENGINEERING_AI_PROVIDER`, `ENGINEERING_AI_EMBEDDING_PROVIDER` mà không in khóa.
3. **Quy tắc bóc tách thể tích đục cho dầm** (bề rộng vùng đục, chồng lấn, xử lý sườn/đáy) — chưa có trong hồ sơ; cần duyệt trước khi tính.
4. **Diện tích quét keo / mài phẳng** có được phép lấy bằng diện tích dán sợi không? Hiện hồ sơ không nói rõ; cần quy tắc.
5. **Độ chính xác của danh sách 45/39 cọc** mới được một người đọc từ ảnh; cần người thứ hai đối chiếu trước khi đưa vào golden set.
6. **Toàn bộ trang bảng khối lượng nhóm II/III** chưa kiểm kê hết; giai đoạn A chỉ xác minh các trang 8, 15, 22, 46.

## 10. Tuân thủ ranh giới

- Không sửa `data/app.db`.
- Không sửa PDF nguồn.
- Không sửa code sản phẩm.
- Không sửa `docs/agent-reports/engineering-ai.md` (báo cáo cũ) — báo cáo này là file mới.
- Không commit.
- Không in secret/token/URL chứa khóa.
- Chỉ đọc DB qua bản sao `/tmp/opencode/rag-diag/*.db`.

## Phụ lục A — Lệnh/tệp bằng chứng

- Bản sao DB: `/tmp/opencode/rag-diag/app-copy.db`, `/tmp/opencode/rag-diag/retrieval-copy.db`.
- Script đo: `/tmp/opencode/rag-diag/measure_retrieval.py`.
- Kết quả retrieval: `/tmp/opencode/rag-diag/retrieval-output.txt`.
- Script xếp hạng: `/tmp/opencode/rag-diag/rank_probe.py`.
- Kết quả xếp hạng: `/tmp/opencode/rag-diag/rank-probe.txt`.
- Ảnh crop bảng: `/tmp/opencode/rag-diag/p8-table-top.png`, `p8-table-bot.png`, `p15-table-top.png`, `p15-table-bot.png`, `p22-khoiluong.png`.

## Phụ lục B — Danh sách cọc phân đoạn 1 (bản đọc từ ảnh)

### B.1 Nhóm 2 — trang 8, 45 cọc

`I3, I4, H2, G2, F3, F4, H5, F7, G8, F10, F12, G11, G14, H14, I16, F19, F22, I24, I25, F27, G29, G32, F33, F34, F36, G35, G38, F39, F40, G41, F42, F43, F45, H47, H48, A2, A5, A8, E146, C146, D147, D148, A148, D150, D151`

### B.2 Nhóm 3 — trang 15, 39 cọc

`I6, I7, I10, I12, I19, I22, I27, I28, I30, I31, I36, I37, I46, H26, H32, G28, F6, F28, F30, F31, F37, F48, E2, E8, E11, E145, E147, C5, C8, C11, C14, B147, B148, B149, B150, A11, A14, A147, A150`

### B.3 Hợp hai nhóm

84 cọc, không trùng. Nếu cần danh sách hợp đầy đủ, nối B.1 + B.2 và giữ nhãn nhóm nguồn; không gộp thành một danh sách phẳng mà không nêu nhóm.
