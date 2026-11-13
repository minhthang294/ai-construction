# Kế hoạch tải PYC/BBNT và cải thiện hỏi đáp hồ sơ

Trạng thái: đề xuất để duyệt, chưa triển khai. Codex điều phối và kiểm tra tích hợp. Hai nhánh độc lập được làm theo thứ tự dưới đây.

## 1. Tải file trong một lần bấm

Hiện `AcceptancePage.tsx` gọi API tạo bản xuất rồi đặt `lastExport`; người dùng phải bấm nút tải riêng. `downloadExport()` đã xử lý bearer token, tên file và kiểm tra URL, nên giữ nguyên hàm này.

- Agent acceptance: sau khi `exportRequest()` hoặc `exportRecord()` thành công, gọi ngay `downloadExport(exported)`. Hiện thông báo theo kết quả tải; nếu tải lỗi, giữ `lastExport` và nút tải lại. Giữ nút này để phục hồi lỗi, không yêu cầu người dùng dùng nó khi tải thành công.
- Phạm vi: `frontend/src/features/acceptance/pages/AcceptancePage.tsx`, test giao diện liên quan; backend không cần đổi nếu API tải hiện tại hoạt động.
- Kiểm: bốn nút PYC/BBNT PDF/XLSX đều tạo rồi tải một lần; file có tên đúng; lỗi tải cho phép thử lại; đăng nhập bearer vẫn hoạt động; kiểm thực tế trên trình duyệt mobile.

## 2. Chẩn đoán trước khi đổi RAG

Hiện pipeline có PyMuPDF/Tesseract, chunk, FTS, sqlite-vec, trích xuất AI theo trang và citation. Mặc định `ENGINEERING_AI_EMBEDDING_PROVIDER=local` là hash từ khóa, không hiểu ngữ nghĩa. `search_chunks()` chỉ nhận chunk có từ trùng câu hỏi hoặc FTS; do đó ngay cả vector tốt cũng không cứu được câu hỏi diễn đạt khác. Chat mặc định là extractive nếu provider AI không được cấu hình. `PageExtraction` hiện chỉ boost trang; không làm nguồn câu trả lời.

- Codex chuẩn bị bộ câu hỏi chuẩn từ hai bộ hồ sơ đã nạp, có đáp án và trang nguồn do người kiểm tra xác nhận. Bao gồm câu hỏi diễn đạt lại, số liệu, bản vẽ, phủ định/không có nguồn và câu hỏi vượt dự án. Không đưa nguyên PDF hoặc dữ liệu nhạy cảm vào Git.
- Ca bắt buộc đầu tiên: “Cầu chính phân đoạn 1 các cọc nào hỏng?”. Người kiểm tra xác nhận trên ảnh bản vẽ tên/số hiệu từng cọc và số trang; nếu hồ sơ không thể hiện danh sách đó, đáp án chuẩn là nêu thiếu chứng cứ, không suy từ phần thuyết minh về cọc nứt nói chung. Kiểm cả các cách viết “phân đoạn I”, “đoạn 1” và “cọc hư hỏng”.
- Agent engineering-ai, chỉ đọc: ghi log cho từng câu hỏi gồm document/chunk count, trạng thái `ready` và `is_effective`, provider đang chạy, top-k và điểm, trang nguồn dự kiến/thực tế, loại lỗi (trích xuất, index, retrieval, answer, citation). Không sửa DB thật khi chẩn đoán.
- Codex chốt baseline: Recall@5 theo trang, tỷ lệ câu trả lời đúng có citation, tỷ lệ từ chối đúng, độ trễ và chi phí. Nếu hai hồ sơ chưa `ready` hoặc không effective, sửa trạng thái/vận hành trước khi thiết kế lại.

## 3. Nâng chất lượng theo lỗi đã đo

- Đích hỏi đáp là từng cấu kiện, không chỉ tóm tắt trang: với mã cọc/dầm và phân đoạn, trả lời tình trạng hư hỏng, chiều sâu đục, chiều dài sửa chữa, quy trình và từng công tác/khối lượng (đục bê tông, quét keo, mài phẳng...). Cần phân biệt số đo trên bản vẽ, chỉ dẫn kỹ thuật chung, khối lượng trong bảng tổng hợp và khối lượng tính suy ra. Mỗi giá trị phải giữ đơn vị, mã cấu kiện, revision, trang và vị trí ô/hình để mở lại nguồn.
- Schema trích xuất hiện chỉ có `key_values` tổng quát và `table_rows` là mảng chuỗi; chưa gắn một giá trị với cọc/dầm cụ thể hay cột bảng. Trước khi làm semantic search, bổ sung một lớp dữ kiện cấu kiện được chuẩn hóa từ các trang/bảng liên quan; đối chiếu mã cọc/dầm qua các trang và chỉ đánh dấu đã kiểm chứng sau khi người xem xác nhận trên ảnh. Không chia khối lượng tổng BOQ cho từng cọc nếu hồ sơ không nêu quy tắc phân bổ.
- Hệ thống phải tự tính khối lượng riêng khi đủ đầu vào và quy tắc bóc tách: lấy kích thước vùng hỏng/sửa chữa và tiết diện, chiều dài, chiều sâu, số mặt/lớp, hệ số hoặc định mức từ đúng bản vẽ/chỉ dẫn; chuẩn hóa đơn vị; áp dụng công thức theo loại công tác; ghi rõ phần cộng, trừ, làm tròn và trường hợp chồng lấn. Bộ công thức được kiểm bằng ví dụ thủ công trước khi dùng cho dữ liệu thật. AI chỉ nhận diện cấu kiện/đầu vào và giải thích; phép tính dùng mã xác định, không để mô hình tự nhẩm hay tự tạo công thức.
- Mỗi kết quả trả `giá trị + đơn vị + loại nguồn (hồ sơ ghi sẵn / hệ thống tính) + công thức ký hiệu + số thay vào + từng nguồn đầu vào + quy tắc bóc tách + revision`. Nếu thiếu một đầu vào hoặc quy tắc có nhiều cách hiểu, chỉ ra đúng phần thiếu/mâu thuẫn và không đưa số khẳng định. Giá trị tính được không ghi đè BOQ gốc hay dữ kiện đã kiểm chứng.
- Agent engineering-ai: ưu tiên semantic embedding tiếng Việt/đa ngữ trên endpoint sẵn có; làm phiên bản index và reindex hai hồ sơ theo cách có thể quay lại. Bỏ điều kiện trùng từ tuyệt đối cho ứng viên vector, nhưng chỉ chấp nhận nguồn khi qua ngưỡng/rerank phù hợp và xác minh quote thực sự có trên trang. Kết hợp FTS cho mã bản vẽ, kích thước và số hiệu. Không dùng hash vector làm bằng chứng ngữ nghĩa.
- Với trang scan OCR yếu, đánh giá AI vision extraction theo trang/ô hoặc tile như nguồn phụ có vị trí trang, trạng thái proposed/verified và dấu vết nguồn. Chỉ đưa vào retrieval khi xác minh được nội dung với ảnh trang; không biến key-value AI thành sự thật đã duyệt. Giữ OCR làm baseline và đường fallback, vì bỏ OCR sẽ mất văn bản có thể tìm kiếm trên nhiều trang.
- Answer: cho mô hình nhận đúng các đoạn được truy hồi, chỉ trả lời với citation trang; khi thiếu chứng cứ thì từ chối. Đánh giá citation trước khi cho hiển thị. Giao diện nêu rõ hồ sơ nào đã sẵn sàng, phạm vi effective/history và lý do không tìm được nguồn.
- Kiểm bằng bộ câu hỏi chuẩn trên bản DB sao chép; yêu cầu tăng Recall@5 và tỷ lệ đáp án đúng so với baseline, không tăng câu trả lời sai có citation. Sau đó mới thử trên dữ liệu thật và điện thoại.
- Ca kiểm theo cấu kiện: “Cọc [mã] đục sâu bao nhiêu?”, “chiều dài sửa chữa?”, “quy trình xử lý?”, “khối lượng đục/quét keo/mài phẳng?” và câu tương tự cho dầm. Với câu “cọc này”, hệ thống chỉ dùng mã cấu kiện đang được chọn trong giao diện hoặc hỏi lại mã; không tự chọn cọc. Kiểm số, đơn vị, công tác, trang nguồn, revision và khả năng chỉ ra dữ liệu thiếu hoặc mâu thuẫn.
- Kiểm tính khối lượng bằng các trường hợp đã bóc tay: một cọc, một dầm, nhiều vùng hỏng, đổi mm/cm/m, diện tích quét keo theo số mặt, thể tích đục theo chiều sâu, phần giao nhau, dữ liệu thiếu, và sai khác với khối lượng tổng hợp. Test phải đối chiếu công thức hiển thị và kết quả số; khi sai khác với BOQ gốc, hiện cả hai và chênh lệch, không tự sửa hồ sơ.

## Điều phối herdr

Khi Codex ở trong pane herdr, kiểm `HERDR_ENV=1`, `herdr pane current`, `herdr agent list`, `herdr pane list`; chỉ điều khiển pane đúng workspace/dự án. Giao agent acceptance nhánh 1, agent engineering-ai phần chẩn đoán nhánh 2; Codex giữ baseline, hợp đồng chung, review và kiểm thử. Không giao code RAG trước khi có baseline. Đóng pane OpenCode idle không được giao việc thuộc AI-Construction sau khi xác nhận `idle/done` và đúng cwd; giữ pane đang làm hoặc bị chặn, không đóng pane dự án khác. Nếu không ở trong herdr, chờ phiên điều phối trong herdr thay vì điều khiển focused session từ bên ngoài.

Ranh giới ghi trong `docs/AGENT_BOUNDARIES.md`; không sửa chung `data/app.db`, không reset dữ liệu hay thay thế PDF nguồn. Sau mỗi nhánh, Codex review diff, chạy test liên quan, rồi full gate và kiểm trình duyệt/điện thoại trước khi công bố hoàn tất.
