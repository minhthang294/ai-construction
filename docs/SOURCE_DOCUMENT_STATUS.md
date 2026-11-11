# Trạng thái hồ sơ nguồn

- Mẫu Excel PYC/BBNT: `/home/thangpham/Downloads/YCNT và BBNT.19.10 - nt thuc te.xlsx` đã được kiểm tra cấu trúc ngày 11/11/2026. Workbook có sheet `DM`, `PYC`, `BBNT` cùng 3 sheet ẩn; đây là hồ sơ có dữ liệu thực, chỉ dùng làm mẫu đọc và sao chép, không ghi đè.
- Bản sao template trong repository: `data/templates/acceptance-original.xlsx`, SHA-256 `e204c40603fc75219e0690ce548d176b64b1b08c27df10d2629ab7c70f8ee382`, trùng file nguồn; không sửa bản này khi xuất.
- Bản vẽ scan, thuyết minh KTKT, chỉ dẫn kỹ thuật, tiêu chuẩn và các PDF khác: chưa được cung cấp trong repository. Người dùng sẽ tải lên sau.
- Kho tri thức AI theo hồ sơ công trình: chưa được kiểm chứng. Không được sinh câu trả lời kỹ thuật riêng của công trình khi chưa có nguồn và citation.
- OCR trên máy: có Tesseract nhưng hiện chỉ có dữ liệu `afr`, `eng`, `osd`; chưa có `vie`. Pipeline cảnh báo và thử `eng` khi thiếu tiếng Việt. Cần cài dữ liệu `vie` trước khi nạp bản vẽ/PDF scan tiếng Việt thật.
