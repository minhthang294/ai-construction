# Danh mục cấu kiện: thiết kế và kế hoạch Sprint 1

## Kiểm kê

Ứng dụng hiện dùng FastAPI, SQLAlchemy, Alembic, SQLite và React. Model nằm trong từng module, không có `backend/app/models/`; test ở `backend/tests/`. Migration trước Sprint 1 là `a7c3e9f2b641`. Quyền dùng `require_project_member` và `require_project_role`; `WorkItem`, báo cáo ngày và nghiệm thu đang là các thực thể riêng. Excel seed có các sheet `DANH_MUC`, `LIEN_KET_CONG_VIEC`, `18_PHAN_DOAN` và chỉ mục bản vẽ; hai PDF không nằm trong `data/`. Không suy ra rằng PDF không có ở nơi private khác.

## Quyết định thiết kế

Giữ WorkItem và các dịch vụ nghiệm thu/báo cáo hiện có; thêm danh mục cấu kiện riêng với ID UUID. Unique theo project, zone, segment, type, canonical code; alias được phân giải trong cùng phạm vi và báo xung đột thay vì tự ghép. Nhóm thiết kế có loại riêng cho cọc/dầm; một cấu kiện có nhiều phạm vi sửa chữa. Nguồn lưu hash, sheet, dòng và giá trị thô; không sao chép dữ liệu nhạy cảm vào fixture công khai. Trạng thái xác minh danh mục, thi công và nghiệm thu độc lập.

API preview nhận file, trả hash, candidates, nguồn, xung đột và cảnh báo; không ghi DB. Commit chỉ nhận batch đã duyệt, kiểm membership/quyền sửa, kiểm lại xung đột trong transaction, ghi audit và idempotency key theo project. Không tự gán nhóm cho phát sinh. Các liên kết DM giữ dòng và chuỗi vị trí gốc; ngày trong seed không được biến thành tiến độ hay xác nhận nghiệm thu. Không tạo cấu kiện giả cho phân đoạn 2–18.

## Kế hoạch

1. Bổ sung migration có thể nâng/hạ và model zone, segment, nhóm, cấu kiện, alias, phạm vi, nguồn và liên kết DM; kiểm thử trên DB tạm và không chạm DB thật.
2. Hoàn thiện parser seed có giới hạn kích thước, kiểm tra định dạng, trùng và nguồn; trả preview qua API có phân quyền. Dữ liệu nguồn chỉ được coi là đề xuất.
3. Tạo commit có duyệt và idempotency, transaction, audit, kiểm xung đột, bảo toàn raw code; test nhập hai lần, quyền và đồng thời.
4. Kiểm thử thực tế 130/45/39/34/949, alias I40-42, phân đoạn 2–18 rỗng; test fixture tổng hợp không chứa dữ liệu riêng tư và migration upgrade/downgrade. Cập nhật hợp đồng API sau khi implementation tồn tại.

## Hiện trạng

Đã có model, migration, API preview/commit và UI duyệt cùng kiểm thử trên database tạm. Commit đối chiếu workbook gửi lại và yêu cầu xác nhận; để sửa candidate phải sửa workbook và xem trước lại. Chưa có lưu trữ nguồn upload hoặc quy trình hợp nhất các lần import có thay đổi nguồn: xung đột cần rà soát thủ công. Các chức năng tiến độ, nghiệm thu và nhật ký thuộc sprint sau.
