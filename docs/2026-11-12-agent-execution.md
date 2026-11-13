# Giao việc OpenCode trong herdr — tải nghiệm thu và RAG cấu kiện

Đọc `docs/2026-11-12-download-rag-plan.md` trước. Trước khi điều phối, dùng `herdr pane current --current` xác nhận pane Codex, cwd và tab của dự án; shell công cụ có thể không kế thừa `HERDR_ENV`. Không sửa `data/app.db`, PDF nguồn, hoặc file ngoài ranh giới trong `docs/AGENT_BOUNDARIES.md`. Hai báo cáo hiện đang có thay đổi của phiên khác; không reset/ghi đè.

## Agent acceptance — làm trước, độc lập

Phạm vi sửa: `frontend/src/features/acceptance/` và test tương ứng.

Yêu cầu: trong `AcceptancePage.tsx`, sau `exportRequest()` và `exportRecord()` thành công, gọi `downloadExport(exported)` ngay. Thành công báo đã tải; nếu tải thất bại, giữ `lastExport`, hiện lỗi và nút tải lại. Không đổi hàm tải có bearer token, kiểm URL và tên file. Bao phủ PYC/BBNT PDF/XLSX. Thêm test luồng một lần bấm và lỗi tải nếu test UI hiện có hỗ trợ; chạy frontend test và build. Báo cáo file đã sửa, test, rủi ro mobile; không commit hoặc sửa shared code.

## Agent engineering-ai — giai đoạn A: chẩn đoán, chỉ đọc

Phạm vi đọc: `backend/app/engineering_ai/`, `frontend/src/features/engineering-ai/`, bản sao DB ở `/tmp` nếu cần. Không thay DB dùng chung. Câu chuẩn đầu tiên: “Cầu chính phân đoạn 1 các cọc nào hỏng?”. Thêm câu theo một cọc và một dầm về chiều sâu đục, chiều dài sửa, quy trình, thể tích đục, diện tích quét keo, mài phẳng. Xác định trang bản vẽ/ô bảng và đáp án trực tiếp bằng ảnh gốc; ghi rõ trường hợp không có dữ kiện. Đo top-5 retrieval của câu hỏi gốc và cách viết tương đương; phân loại lỗi trích xuất, gắn mã cấu kiện, index, retrieval, answer/citation. Kiểm provider thực tế mà không in khóa hoặc URL chứa khóa. Ghi báo cáo vào `docs/agent-reports/engineering-ai.md`; chưa sửa pipeline.

## Codex — cổng sau giai đoạn A

Review báo cáo và đối chiếu ảnh gốc. Chốt bộ dữ kiện chuẩn: mã cấu kiện, vị trí/nhóm, tình trạng, kích thước, công tác, đơn vị, nguồn trang/ô, revision, loại số liệu trực tiếp hay tính. Chốt công thức bóc tách từng công tác từ hồ sơ/quy tắc được người dùng chấp nhận; nếu thiếu quy tắc thì nêu giả định để duyệt trước khi tính thật. Giao giai đoạn B khi baseline đủ rõ.

Đã chốt ca đối chiếu trong `docs/agent-reports/engineering-ai-rag-diagnosis-2026-11-12.md`: cầu chính phân đoạn 1 có 45 cọc nhóm 2 ở trang bản vẽ 8 và 39 cọc nhóm 3 ở trang 15, tổng 84 mã không trùng. `I49` nằm ở phân đoạn 2; bản nháp đầu của agent đã đếm sai ranh giới này và đã được sửa sau khi Codex xem ảnh gốc. Ca H77 có số liệu trực tiếp ở trang 22 nhưng mã không có trong chunk index. Ca dầm I-30-31 chỉ đủ kích thước và diện tích dán sợi trực tiếp; chưa đủ quy tắc để tính diện tích quét keo/mài phẳng hoặc thể tích đục.

## Agent engineering-ai — giai đoạn B: triển khai sau cổng A

Trong `backend/app/engineering_ai/` và frontend feature tương ứng: trích xuất dữ kiện theo cấu kiện từ bảng/bản vẽ; gắn citation đúng trang/vùng, revision và trạng thái xác minh. Thêm tìm kiếm theo mã cấu kiện cùng semantic/lexical retrieval, giữ project/effective scope. Tính toán bằng code xác định từ đầu vào đã kiểm, chuẩn hóa đơn vị, hiện công thức ký hiệu, số thay vào và nguồn từng số; tách kết quả tính khỏi BOQ gốc. Thiếu hoặc mâu thuẫn đầu vào thì không trả số. Thêm test đối chiếu các ca bóc tay, từ chối khi thiếu dữ kiện, cách hỏi “cọc này” không có mã, và câu hỏi về cọc/dầm không thuộc dự án. Không thêm dependency nếu provider hiện có đủ dùng. Báo cáo diff/test để Codex review trước tích hợp.

Lượt B lớn ban đầu không tạo diff sau hơn 5 phút suy nghĩ, nên Codex đã dừng và chia nhỏ. Agent mới `component_facts` ở `w1:p3S` đang làm B1: format dữ kiện cấu kiện trong `PageExtraction.extraction_json`, validation và calculator thuần với test synthetic; chưa nối DB/chat. Codex sẽ review B1 trước khi giao B2 retrieval/API và B3 UI/reindex.

Trạng thái cuối lượt: B1 hoàn thành trong `page_extraction.py`, `quantity_calc.py` và test; Codex nối prompt mới vào `scripts/deepseek_page_extract.py` và viết `component_search.py` cùng test truy vấn verified/effective/project. Agent B2a bị lỗi kết nối OpenCode `ECONNRESET`, không tạo diff; pane `w1:p3S` đã đóng. Lần chạy thử DeepSeek trang 8 vào `/tmp/opencode/component-extract-p8` chờ nhiều giờ, không tạo JSON và đã dừng; không ghi DB thật. Full gate sau đó: 230 backend, 98 frontend, build pass. Chưa nối chat/UI hoặc reindex hồ sơ thật.

DB dùng chung hiện có 239 extraction `proposed`, 2 `verified`; cả hai trang verified chưa có `component_facts`. Vì vậy đường truy vấn mới hiện không có dữ kiện cấu kiện để trả lời. Phải khôi phục kết nối OpenCode/DeepSeek, trích xuất lại trang liên quan, đối chiếu ảnh và xác minh trước khi tích hợp chat hoặc chạy trên toàn bộ hồ sơ. Không đánh dấu tự động các bảng OCR sai là verified.

## Cổng hoàn tất do Codex giữ

Review mọi diff và kiểm `git diff --check`; chạy test module, full `scripts/verify_all.sh`, smoke API trên bản DB sao chép, kiểm tải trên trình duyệt và mobile khi có thiết bị. So câu trả lời của bộ chuẩn với baseline: mã cấu kiện, giá trị, đơn vị, công thức, nguồn và khả năng từ chối. Không công bố tính khối lượng đúng khi chưa đối chiếu bóc tay.

Pane: sau khi xác nhận trạng thái `idle/done` và cwd thuộc AI-Construction, dùng pane đang rảnh cho hai agent; đóng pane OpenCode không nhận việc thuộc dự án này. Không đóng pane workspace/dự án khác, pane đang `working/blocked/unknown`, hoặc pane Codex điều phối. Lượt này acceptance ở `w1:p3J`, engineering-ai ở `w1:p3R`, Codex ở `w1:p3Q`; hai agent đã nhận prompt và đang `working`.
