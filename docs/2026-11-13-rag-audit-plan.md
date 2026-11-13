# Kế hoạch sửa RAG hồ sơ công trình (13/11/2026)

## Bằng chứng hiện tại

- Hai PDF có 241 trang, 248 bản trích xuất: 239 `proposed`, 9 `verified`. Chỉ 116 dữ kiện cấu kiện đã xác minh; H77 là cọc duy nhất có bộ số đo và khối lượng đã xác minh, dầm I-30-31 là dầm duy nhất có số đo chi tiết.
- F27 có số đo ở bảng AI trích xuất trang 25, chưa được kỹ sư xác minh. Không được trình bày là số liệu đã xác minh.
- Câu `diện tích quét keo cọc F27` trả chiều dài vết nứt; câu `dầm I-30-31 chiều dài vết nứt` trả chiều dài dán sợi. Đây là lỗi sai trường dữ liệu, mức ưu tiên cao nhất.
- Tra nhóm 2 đọc được 198 mã duy nhất từ 257 lượt đọc bảng đề xuất, có dòng thiếu vị trí và mã mơ hồ. Không được gọi 198 là tổng cọc chính thức.
- Thành viên chỉ có quyền xem hiện có thể gọi API xác minh bản trích xuất; nạp lại tài liệu có thể bỏ lại bản trích xuất gắn với page ID cũ.

## Thực hiện

1. Chặn dữ kiện sai: xác định đúng ý định trường đo, nhóm, phân đoạn, vị trí trước khi trả lời. Nếu thiếu đúng ô hoặc nguồn mơ hồ, trả lời chưa xác định và đưa trang đối chiếu. Mọi số liệu từ `proposed` phải có nhãn rõ.
2. Bảo vệ dữ liệu: yêu cầu quyền biên tập cho lưu/xác minh; xử lý vòng đời bản trích xuất khi nạp lại, không làm mất dữ kiện đã xác minh.
3. Kiểm tra câu hỏi thực: H77 (sâu, nứt, keo), I-30-31 (sâu sườn/đáy), F27 (sâu đề xuất), nhóm 1/2, mã không tồn tại, câu hỏi sai trường, quy trình nhóm 2. Đối chiếu citation với trang và hàng nguồn. Chạy toàn bộ backend tests và thử API sau khi tải lại backend.
4. Giai đoạn tiếp theo: tăng độ phủ bằng trích xuất có cấu trúc theo bảng, lưu nguồn hàng/cột và phiên bản, cho kỹ sư duyệt theo lô, đo coverage theo cọc/dầm/trường dữ liệu. Chỉ cam kết hỏi đáp cho mọi cấu kiện sau khi dữ liệu và bộ đánh giá đạt ngưỡng.

## Điều kiện nghiệm thu

- Không trả số đo của trường khác hoặc phần việc khác; không trả số khi nhóm/phân đoạn mâu thuẫn.
- Số đo có đơn vị, trang nguồn, trạng thái xác minh; khối lượng tính toán có công thức và nguồn của từng đầu vào.
- Dữ liệu không có hoặc mơ hồ phải được báo rõ, không dựng câu trả lời từ một từ khớp trong chunk.
- Quyền xem không thể xác minh; nạp lại không tạo bản trích xuất mồ côi hoặc âm thầm xóa bản đã xác minh.
