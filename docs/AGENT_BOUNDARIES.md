# Ranh giới agent

Codex sở hữu `backend/app/core`, `backend/app/models`, `backend/alembic`, `frontend/src/app`, auth, shared API/contracts, integration, README và scripts. Agent không sửa các đường dẫn này; đề xuất thay đổi shared trong report.

| Agent | Chỉ được sửa |
| --- | --- |
| site-report | `backend/app/site/`, `frontend/src/features/site/`, test tương ứng, `docs/agent-reports/site-report.md` |
| engineering-ai | `backend/app/engineering_ai/`, `frontend/src/features/engineering-ai/`, test tương ứng, `docs/agent-reports/engineering-ai.md` |
| acceptance | `backend/app/acceptance/`, `frontend/src/features/acceptance/`, test tương ứng, `docs/agent-reports/acceptance.md` |

Các agent đọc hợp đồng chung, không sửa code của nhau. Nếu thiếu shared interface, ghi rõ yêu cầu trong report và tiếp tục phần độc lập. Không merge vào main, không tự thêm dữ liệu công trình giả, không chỉnh file Excel nguồn.
Không xóa/reset `data/app.db` để chạy test; dùng `DATABASE_URL` trỏ tới SQLite tạm trong `/tmp` hoặc fixture in-memory. Không sửa dữ liệu ứng dụng dùng chung.
