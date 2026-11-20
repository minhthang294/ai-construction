# Kế hoạch xóa công trình và cải thiện ảnh hiện trường

## 1. Xóa công trình có xác nhận

- Thêm nút **Xóa công trình** trong phần Công trình ở `frontend/src/app/CorePages.tsx`. Hộp thoại hiển thị tên công trình, tác động của thao tác và hai lựa chọn **Hủy** / **Xóa công trình**. Chặn gửi lặp. Sau khi thành công, làm mới danh sách và chuyển sang công trình còn truy cập được.
- Kiểm tra các quan hệ với danh mục DAP, tiến độ, hồ sơ nghiệm thu, nhật ký và file đính kèm trước khi thiết kế API ở `backend/app/core/router.py`. Ưu tiên xóa mềm để có thể khôi phục và bảo toàn hồ sơ đã phát hành. Yêu cầu quyền quản trị phù hợp, ghi audit theo ID công trình và chặn truy cập thường vào công trình đã xóa.
- Kiểm thử hủy xác nhận, quyền xóa, truy cập khác công trình, tải lại danh sách và bảo toàn dữ liệu liên quan.

## 2. Chụp và chọn ảnh trên điện thoại

- Trong `frontend/src/features/site/components/PhotoCapture.tsx`, tách **Chụp ảnh** dùng input có `capture="environment"` và **Chọn ảnh từ máy** dùng input riêng có `accept="image/*"`, hỗ trợ chọn nhiều ảnh. Đưa hai nguồn vào cùng luồng xem trước và tải lên.
- Thử trên Safari iPhone và Chrome Android. Kiểm tra mở đúng camera/thư viện, hủy chọn, chọn lại cùng ảnh và ảnh HEIC. Khi trình duyệt không đọc được định dạng, báo rõ cách chọn lại ảnh.

## 3. Watermark và nén trước khi tải

- Ghi ngày giờ và vị trí trực tiếp lên pixel của ảnh tải lên. Với ảnh chụp mới, lấy giờ thiết bị khi chụp và xin quyền vị trí. Với ảnh có sẵn, ưu tiên metadata EXIF đọc được và thông tin người dùng xác nhận. Hiển thị nguồn thời gian/vị trí ở bước xem trước. Khi thiếu thông tin, cho nhập hoặc hiển thị **Chưa xác định**. Có thể ghi vị trí công trường bằng chữ cùng tọa độ nếu người dùng cho phép.
- Chuẩn hóa hướng ảnh, thu cạnh dài về tối đa **1.920 px**, rồi vẽ watermark bằng Canvas với cỡ chữ theo kích thước ảnh. Thử nén **JPEG chất lượng 0,82**, giảm dần đến 0,65 nếu vượt **500 KB**. Xem các giá trị này là cấu hình thử nghiệm. Đo dung lượng và thời gian tải trên ảnh công trường thực tế, đồng thời kiểm tra khả năng đọc vết nứt, thước đo và watermark trước khi chốt.
- Dùng cùng ảnh đã xử lý cho tải trực tiếp và hàng đợi offline. Giữ mã chống trùng khi tải lại. Kiểm tra loại và giới hạn file phía server. Thử mất mạng, từ chối GPS, ảnh xoay và ảnh độ phân giải cao.

## 4. Xóa ảnh hiện trường

- Thêm nút **Xóa ảnh** kèm xác nhận ngay trên từng ảnh. Bổ sung API xóa theo dự án trong `backend/app/site/router.py` và tích hợp vào API client hiện trường. Kiểm tra quyền và các liên kết bằng chứng trước khi xóa. Với ảnh đã dùng cho tiến độ, nhật ký đã duyệt hoặc nghiệm thu, giữ bằng chứng và báo rõ nơi đang sử dụng ảnh.
- Kiểm thử hủy xác nhận, xóa ảnh chưa được liên kết, ảnh đã dùng làm bằng chứng, truy cập khác dự án và tải lại danh sách. Kiểm tra việc xóa ảnh khỏi hàng đợi local để ảnh không tự tải lên lại.

Triển khai trước trên demo. Kiểm tra trên điện thoại thật trước khi đưa lên VM DAP.

## 5. Thứ tự và tên bước thi công DAP

- Màn hình tiến độ dùng vị trí bước theo từng công tác đã gắn với cấu kiện và phạm vi sửa chữa. Màu xanh cho hoàn thành, vàng cho đang làm và đỏ cho chưa bắt đầu. Trạng thái nghiệm thu hiển thị riêng.
- `scripts/order_dap_stages.py --database <db>` xem trước việc chỉnh tên và thứ tự của danh mục DAP. Sau khi sao lưu đúng database, dùng thêm `--apply` để ghi thay đổi và audit. Script giữ nguyên định danh bước, khối lượng thiết kế và sự kiện tiến độ. Bản cập nhật local đã thực hiện trên database demo.
