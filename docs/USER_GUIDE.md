# Hướng dẫn sử dụng

1. Đăng nhập bằng tài khoản do quản trị tạo. Đổi mật khẩu bằng nút **Đổi mật khẩu** ở header.
2. Trong **Công trình**, tạo/chọn công trình. Có thể nhập tiêu đề báo cáo riêng cho công trình.
3. Trong **Công việc**, thêm công việc trực tiếp hoặc tải Excel có sheet `DM`, xem trước từng dòng rồi xác nhận nhập. Không có dữ liệu công trình nào được nhập tự động.
4. Trong **Cấu kiện**, nhập danh mục cọc/dầm theo phân đoạn (tải Excel và xem trước, hoặc thêm tay). Kiểm tra công đoạn và phạm vi sửa chữa trước khi ghi tiến độ.
5. Trong **Hiện trường**, chọn ngày, nhập nhân lực, công việc, kế hoạch ngày sau, ghi chú và ảnh. `0` nghĩa là không có người; ô trống nghĩa là chưa cập nhật. Dữ liệu chưa đồng bộ được giữ trên thiết bị và hiển thị trạng thái chờ.
6. Ảnh có thể gắn với cấu kiện. Xác nhận chú thích/loại ảnh trước khi dùng làm chứng cứ; ảnh gốc được lưu riêng.
7. Duyệt nội dung trước khi xuất Zalo text, PDF, Word hoặc ZIP. Hệ thống không tự gửi vào nhóm Zalo.
8. **Ghi tiến độ từ tin nhắn**: dán tin nhắn Zalo hiện trường, xem lại dòng công tác/cấu kiện và trả lời các câu hỏi (trạng thái, công đoạn, mã lạ, ngày tương lai), rồi ghi. Sau khi ghi có thể sửa hoặc hoàn tác đợt ghi; tiến độ **không** tạo nghiệm thu.
9. **Đợt thi công**: tạo đợt để gom cấu kiện ở nhiều khu, thêm/bớt cấu kiện và lọc danh sách theo đợt khi ghi tiến độ hoặc lập PYC.
10. **Tham số thiết kế `t`**: chiều dày đục của từng cọc được nhập bằng `scripts/import_design_parameters.py` (xem trước rồi mới `--commit`). Hỏi AI “chiều dày t của cọc …” để tra giá trị kèm nguồn.
11. Trong **Hỏi AI**, đặt câu hỏi về cấu kiện, tiến độ, đợt thi công hoặc hồ sơ. AI trả lời trên dữ liệu đã trích xuất theo trang và cơ sở dữ liệu cấu kiện; mở citation để đối chiếu đúng trang. Không có upload PDF/OCR trong ứng dụng.
12. Trong **Nghiệm thu**, xem danh sách **Chờ nghiệm thu** (cấu kiện đã hoàn thành, chưa có BBNT xác nhận). Nếu đi từ màn hình khác, bộ lọc công đoạn/đợt hiển thị chip **Đang lọc** và nút **Xem tất cả**. Chọn cấu kiện rồi bấm **Tạo PYC nháp**; phiếu nháp điền sẵn ngày làm việc kế tiếp, vị trí và công đoạn nhưng **chưa xác nhận nghiệm thu**. Điền checklist Có/Không/Chưa xác nhận; người có quyền mới xác nhận kết quả. Mẫu Excel gốc không bị chỉnh sửa khi xuất.

Câu trả lời AI về công trình chỉ là thông tin tham khảo cho đến khi kỹ sư đối chiếu citation/trang gốc; kết quả trích xuất `proposed` chưa được xác minh.
