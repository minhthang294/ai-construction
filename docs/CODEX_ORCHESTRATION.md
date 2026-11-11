# Điều phối OpenCode

Ba cấu hình trong `.opencode/agents/` dùng model `opencode-go/deepseek-v4.1-flash`: `site-report-agent`, `engineering-ai-agent`, `acceptance-agent`. Mỗi agent chỉ sửa phạm vi trong `docs/AGENT_BOUNDARIES.md` và cập nhật báo cáo tương ứng trong `docs/agent-reports/`.

OpenCode v2.2.6 trên máy dùng `opencode debug agents` để liệt kê agent; `opencode agent list` và `opencode run --dir` không có ở bản này. Script chuyển thư mục làm việc rồi gọi `opencode run --agent`.

Ngày 11/11/2026, repository ban đầu không có `.git`, nên không thể tạo Git worktree. Ba agent được chạy trong ba pane riêng của herdr cùng tab, giao diện OpenCode tương tác, với phạm vi file tách biệt. Codex sở hữu shared core, migration, tích hợp router/frontend, kiểm thử và quyết định cuối cùng. Không dùng `--auto`.

`scripts/run_opencode_agents.sh` và `.ps1` cung cấp lệnh chạy batch có log JSON. Chạy batch chỉ khi không có ba agent tương tác đang hoạt động. Với Git sạch, script tạo ba worktree/branch riêng và chạy song song; với Git bẩn hoặc chưa có Git, script chạy tuần tự trong thư mục hiện tại. Không reset, stash, commit hay tự merge thay người dùng.
