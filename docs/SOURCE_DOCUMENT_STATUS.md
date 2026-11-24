# Trạng thái hồ sơ nguồn

- Mẫu Excel PYC/BBNT: workbook người dùng cung cấp đã được kiểm tra cấu trúc ngày 11/11/2026. Workbook có sheet `DM`, `PYC`, `BBNT` cùng 3 sheet ẩn; đây là hồ sơ có dữ liệu thực, chỉ dùng làm mẫu đọc và sao chép, không ghi đè.
- Bản sao template trong repository: `data/templates/acceptance-original.xlsx` (SHA-256 ghi trong lịch sử bàn giao); không sửa bản này khi xuất.
- Bản vẽ scan, thuyết minh KTKT, chỉ dẫn kỹ thuật, tiêu chuẩn và các PDF khác không nằm trong repository. Khi có, hồ sơ được đưa vào DB/storage đã duyệt và trích xuất offline; ứng dụng không upload PDF/OCR.
- Kho tri thức AI theo hồ sơ công trình: dữ liệu trang và kết quả trích xuất đã có trong môi trường demo, nhưng phần lớn vẫn `proposed`. Chỉ dữ liệu `verified` mới được coi là thông tin tin cậy.
- Không được sinh câu trả lời kỹ thuật riêng của công trình khi chưa có nguồn và citation. Câu trả lời thiếu nguồn phải từ chối thay vì suy đoán.
