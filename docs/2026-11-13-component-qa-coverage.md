# Hỏi đáp theo mã cọc và dầm

## Mục tiêu

Người dùng hỏi theo mã cấu kiện, nhóm, phân đoạn hoặc vị trí. Câu trả lời phải nêu số liệu đúng trường, đơn vị, trang nguồn và trạng thái xác minh. Các phép tính khối lượng phải hiện công thức, kích thước đầu vào và trang của từng đầu vào.

## Đã nối vào hỏi đáp

- Cọc: tra mã chính xác trong hàng bảng đề xuất để lấy `t (cm)`, `L1–L4 (m)` và chiều dài vết nứt. Ô trống không được kế thừa tự động từ hàng trên.
- Dầm: tra mã chính xác trong hàng bảng đề xuất để lấy kích thước và khối lượng ghi sẵn; không coi chiều dài dầm là chiều dài vết nứt.
- Nhóm cọc: đọc danh sách từ bảng mặt bằng theo nhóm; đếm mã theo vị trí và phân đoạn, ghi rõ mã OCR chưa chắc chắn. Nhóm 1 có 6 dòng trên TK-01; mã `299` cần đối chiếu lại.
- Mọi dữ kiện đề xuất đều có citation và cảnh báo chưa được kỹ sư xác minh. Dữ kiện đã xác minh được ưu tiên khi cùng trường.

## Chưa đạt để cam kết trả lời mọi cấu kiện

Cơ sở dữ liệu hiện có 2 PDF hiệu lực, 239 trang trích xuất đề xuất và 9 trang đã xác minh. Nhiều bản vẽ dầm chỉ có chú thích tự do hoặc ảnh scan; bảng khối lượng theo nhóm chưa liên kết an toàn tới từng mã. Một số hàng OCR sai hoặc mâu thuẫn. Vì vậy không được hứa một số đo cho mã không có nguồn rõ ràng.

### Mốc đo trên `data/app.db` ngày 13/11/2026

| Chỉ số | Kết quả |
| --- | ---: |
| Hồ sơ / trang | 2 / 241 |
| Bản trích xuất đề xuất / đã xác minh | 239 / 9 |
| Trang có `component_facts` đã xác minh | 7 |
| Cọc có trạng thái hư hỏng đã xác minh | 84 mã |
| Cọc có chiều sâu đục và khối lượng đã xác minh | 1 mã: H77 |
| Dầm có kích thước và diện tích đã xác minh | 1 mã: I-30-31 |
| Nhóm 1 / 2 / 3 từ bảng mặt bằng đề xuất | 6 / 198 / 140 mã sau lọc trùng |

Số mã nhóm 2 và 3 chỉ là kết quả đọc bảng đề xuất: lần lượt có 257 và 193 lượt đọc trước lọc trùng, nhiều dòng chưa xác định được vị trí. Nhóm 1 có mã `299` chưa rõ tiền tố; nhóm 2 có dòng `M? (BỊ CẮT)`; nhóm 3 có `15`, `14` không đủ dạng mã. Không dùng các số trên làm tổng cọc chính thức. F27 có trạng thái hư hỏng đã xác minh ở trang 8; chiều sâu đục nằm trong bảng đề xuất trang 25, nên phải gắn nhãn chưa xác minh.

### Điều kiện nghiệm thu hỏi đáp

1. Mỗi số đo phải có citation đúng hồ sơ, trang và hàng/cột hoặc vùng chú thích. Giá trị đề xuất và đã xác minh phải phân biệt trong câu trả lời.
2. Mã cọc/dầm phải khớp chính xác và đúng phiên bản hiệu lực; không dùng số liệu của mã gần giống, mã trùng ở vị trí khác hoặc bản vẽ cũ.
3. Câu hỏi đếm phải loại trùng, bỏ dòng chữ ký/khung tên, và nói rõ mã mơ hồ. Nếu thiếu vị trí thì không tự phân bổ vào Cầu chính/Cầu dẫn.
4. Khối lượng tính mới phải hiện công thức, đơn vị và nguồn của từng kích thước đầu vào; không gán khối lượng nhóm cho một cấu kiện.
5. Thiếu dữ kiện hoặc có hai nguồn mâu thuẫn mà chưa phân giải thì trả lời chưa đủ căn cứ, kèm phần đã biết; không tự tạo số.

Bộ hồi quy dùng fixture đã rà bằng mắt ở `backend/tests/engineering_ai/test_component_qa_replay.py`, cùng các kiểm thử bảng đề xuất và nhóm hiện có. Chạy bằng `PYTHONPATH=backend .venv/bin/pytest -q backend/tests/engineering_ai/test_component_qa_replay.py backend/tests/engineering_ai/test_component_chat.py backend/tests/engineering_ai/test_pile_group_lookup.py`. Bài kiểm thử này không chứng minh độ phủ cho toàn bộ 241 trang; cần chạy đánh giá trên dữ liệu thật sau khi mở rộng phần xác minh.

## Bước tiếp theo

1. Chuẩn hóa mỗi hàng/bảng và chú thích bản vẽ thành dữ kiện `mã → trường → giá trị → đơn vị → trang/hàng/cột → trạng thái`, giữ mã ghép/range riêng.
2. Kiểm tra tự động số cọc, mã, đơn vị và mâu thuẫn giữa mặt bằng, thống kê sửa chữa và bảng khối lượng; đưa các hàng mơ hồ vào danh sách kỹ sư duyệt.
3. Tạo chỉ mục theo mã cấu kiện cho dầm trên cả chú thích và bảng, rồi mở rộng cùng quy tắc dẫn nguồn cho độ sâu đục, chiều dài vết nứt, phạm vi sửa chữa.
4. Nối bảng khối lượng với từng mã chỉ khi khớp đồng thời nhóm, vị trí, kích thước và loại công tác. Tính bằng công thức xác định, hiển thị số đầu vào và không tự cộng tổng nhóm vào một cấu kiện.
5. Tạo bộ câu hỏi kiểm thử từ mọi mã có dữ kiện, gồm cách hỏi tương đương và câu cố tình nhầm mã/nhóm/phiên bản; chỉ công bố độ bao phủ sau khi chạy trên dữ liệu thật.
