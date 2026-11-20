# Tiến độ mặc định và mặt bằng sửa chữa DAP

## 1. Suy ra tiến độ từ các bước đã hoàn thành

- Dùng thứ tự đã rà để đề xuất quan hệ trước–sau theo từng biện pháp. Chỉ suy ra hoàn thành khi bước sau có bản ghi hoàn thành và bước trước là điều kiện của bước đó, trong cùng cấu kiện và phạm vi sửa chữa. Công tác song song hoặc tùy áp dụng cần quan hệ riêng.
- Tính trạng thái khi đọc, dùng chung với danh sách, chi tiết và các bộ lọc theo bước. Hiển thị nhãn **Suy ra từ bước sau** và bước nguồn. Dữ liệu thực tế được ưu tiên. Nếu bước trước có trạng thái mâu thuẫn, giữ nguyên và hiện cảnh báo. Không suy ra khối lượng, ngày thi công hoặc nghiệm thu. Nhật ký xuất tiếp tục dựa trên sự kiện thực tế đủ điều kiện.
- Kiểm tra cọc và dầm, nhiều phạm vi trên cùng cấu kiện, công tác song song, bước chưa gắn và tình huống bước sau được sửa trạng thái.

## 2. Mặt bằng tương tác dựa trên bản vẽ

- Làm thử **Phân đoạn 2 – Cầu chính**. Đối chiếu chỉ mục mặt bằng và các bảng mã cọc/dầm với trang bản vẽ. Lưu điểm cho cọc và đoạn hoặc vùng cho dầm, kèm ID cấu kiện, ID bản vẽ, số trang, tọa độ chuẩn hóa và trạng thái duyệt. Dầm nhiều nhịp có thể có nhiều vùng cho cùng ID. Giữ riêng các vị trí chưa khớp mã để rà.
- Hiển thị lớp đánh dấu trên ảnh mặt bằng đã cắt vùng cần xem. Lọc cọc/dầm, phạm vi phát sinh và trạng thái thi công. Hỗ trợ thu phóng, kéo, tìm mã và mở chi tiết cấu kiện bằng ID. Tận dụng quyền dự án và API chi tiết hiện có. Ảnh bản vẽ và dữ liệu định vị theo dự án lưu riêng.
- So từng vị trí mẫu với bản vẽ. Kiểm tra các mã lặp giữa phân đoạn, dầm liền nhịp, điểm chạm chồng nhau và thao tác trên điện thoại. Mở rộng các phân đoạn khác sau khi duyệt mẫu.

## 3. Phân công khi bắt đầu

- **OpenCode engineering-ai** đối chiếu trang bản vẽ và lập bản nháp vị trí có nguồn.
- **OpenCode site-report** triển khai tiến độ suy ra và giao diện mặt bằng với danh sách file riêng cho từng phần.
- **Codex** chốt hợp đồng dữ liệu, kiểm quyền, tích hợp và kiểm thử demo local. Chờ duyệt mẫu trước khi mở rộng hoặc đưa lên VM.

## 4. Ghi tiến độ theo ngày ở hiện trường

- Mặc định ngày hiện tại. Chọn khu vực, phân đoạn và công tác từ danh mục. Tích đúng mã cấu kiện đã làm, chọn trạng thái. Có thể sao chép các mã còn phù hợp từ công tác trước và bỏ chọn từng mã.
- Mỗi công tác có danh sách cấu kiện riêng. Chỉ hỏi chọn phạm vi hoặc bước cụ thể khi một cấu kiện có nhiều lựa chọn. Xem lại ngày, công tác và mã trước khi lưu.
- Lưu tất cả dòng trong một giao dịch, cùng khóa chống ghi trùng khi tải lại. Khối lượng tổng nếu có thuộc dòng công tác. Sự kiện từng cấu kiện chỉ ghi trạng thái trong luồng này.
