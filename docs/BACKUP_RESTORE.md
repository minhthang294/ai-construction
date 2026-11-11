# Sao lưu và phục hồi

Sao lưu khi ứng dụng đang chạy:

```bash
python3 scripts/backup.py /path/to/backup.tar.gz
```

Script dùng SQLite backup API để chụp DB nhất quán, rồi đóng gói `data/storage` (file gốc, file xuất) và `data/templates` (template đã sao chép). Archive phải nằm ngoài `data/`, được tạo với quyền `0600` và không ghi đè bản sao lưu cũ; archive chứa tài liệu công trình.

Phục hồi vào **thư mục mới, trống**:

```bash
python3 scripts/restore.py /path/to/backup.tar.gz /path/to/new-data
```

Script từ chối ghi đè thư mục đã có dữ liệu và từ chối đường dẫn/loại file nguy hiểm trong archive. Kiểm tra DB, file gốc và quyền thư mục trước khi đổi cấu hình ứng dụng sang dữ liệu phục hồi. Nếu dùng các biến `*_STORAGE` trỏ ngoài `data/storage`, sao lưu riêng các thư mục đó.
