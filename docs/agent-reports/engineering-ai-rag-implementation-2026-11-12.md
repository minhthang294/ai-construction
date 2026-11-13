# Hỏi đáp cấu kiện — kết quả triển khai 12/11/2026

- OpenCode trong herdr thực hiện luồng chat cấu kiện, audit dữ liệu và fixture ảnh gốc; Codex kiểm diff, sửa truy hồi, bổ sung công thức, replay và nhập dữ liệu. Các pane OpenCode của dự án đã đóng khi xong.
- Chat tra `component_facts` trên bản trích xuất `verified` của hồ sơ `ready/effective`, lọc theo công trình, mã cấu kiện, phân đoạn và nhóm. Không dùng bản `proposed` để trả lời hoặc tăng hạng retrieval. Trả citation trang/sheet; từ chối số liệu thiếu hoặc công tác khác.
- Đã đối chiếu và nhập 7 trang vào `data/app.db`: bản vẽ 7, 8, 15, 22, 46; thuyết minh 32, 33. Tổng 116 fact. Bản sao trước nhập: `data/storage/backups/app-before-rag-import-2026-11-12.db` (SHA-256 `5171408347a7f6cef86f08b1cc770f126dfb678d2c9dbe95f69278c827678c75`).
- Replay trên bản sao và đọc lại DB thật: cầu chính phân đoạn 1 có 45 cọc nhóm 2 + 39 cọc nhóm 3, không có I49; H77 có sâu đục 1 cm, dài sửa 0,2 m, thể tích đục 0,003 m³, diện tích keo 0,304 m² và mài 1,280 m²; dầm I-30-31 có diện tích dán sợi 4,560 m². Hệ thống tính lại diện tích dán sợi: `1,9×0,2×4 + 1,6×0,25×7 + 1,6×0,15×1 = 4,560 m²`, hiển thị bên cạnh số nguồn.
- Quy trình H77 và dầm I-30-31 được nối từ phân loại nhóm trên bản vẽ sang mục 4.2/4.3 thuyết minh. Cọc nhóm 2 có quy trình trang 32–33. Cọc nhóm 3 chưa tìm thấy quy trình riêng, nên chat từ chối thay vì suy từ nhóm khác.
- Kiểm thử cuối: 256 backend, 98 frontend và build đều qua; `PRAGMA integrity_check` của DB thật trả `ok`.

## Giới hạn còn lại

- Mới làm giàu 7/241 trang của hai hồ sơ. Các cấu kiện khác chưa có fact có thể vẫn bị từ chối; chưa chạy lại toàn bộ OCR/AI extraction.
- Các fact được agent AI và Codex đối chiếu ảnh, chưa có chữ ký kỹ sư. `verified_by` đang rỗng; trước dùng để nghiệm thu/BOQ cần kỹ sư rà soát. Các trang bản vẽ cũ không lưu `page_sha256` do đường dẫn render không qua kiểm tra root hiện tại.
- Quy trình là chỉ dẫn theo nhóm, không phải bản hướng dẫn riêng cho từng mã. Khối lượng đục/keo/mài H77 là số bảng ghi sẵn; hồ sơ chưa có đủ kích thước để tính độc lập chúng.
- Chưa kiểm thao tác trên trình duyệt/mobile vì không có dịch vụ ứng dụng chạy ở cổng 8765 trong phiên này.
