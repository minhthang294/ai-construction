import { useState } from "react";

type Props = {
  token: string;
  onClose: () => void;
  /** Called after the backend accepted the change and revoked the token. */
  onSuccess: () => void;
};

type ErrorBody = { detail?: unknown; code?: string };

function errorMessage(body: ErrorBody, status: number): string {
  if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  if (body.detail && typeof body.detail === "object") {
    const detail = body.detail as { message?: unknown };
    if (typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }
  }
  return `Đổi mật khẩu thất bại (HTTP ${status}).`;
}

export default function ChangePasswordDialog({
  token,
  onClose,
  onSuccess,
}: Props) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!currentPassword) {
      setError("Nhập mật khẩu hiện tại.");
      return;
    }
    if (newPassword.length < 12) {
      setError("Mật khẩu mới phải có ít nhất 12 ký tự.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Xác nhận mật khẩu mới không khớp.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("Mật khẩu mới phải khác mật khẩu hiện tại.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/v1/auth/change-password", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as ErrorBody;
        setError(errorMessage(body, response.status));
        return;
      }
      // Backend revokes the current token; the shell must return to login.
      onSuccess();
    } catch {
      setError("Không kết nối được máy chủ. Thử lại khi có mạng.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-3 sm:items-center"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="change-password-title"
        className="w-full max-w-md rounded-2xl bg-white p-4 shadow-xl sm:p-6"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="change-password-title" className="text-lg font-semibold">
              Đổi mật khẩu
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Sau khi đổi thành công, phiên hiện tại sẽ kết thúc và bạn cần đăng nhập
              lại.
            </p>
          </div>
          <button
            type="button"
            className="min-h-9 rounded-lg px-2 text-sm text-slate-600 disabled:opacity-50"
            aria-label="Đóng"
            disabled={submitting}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <form className="mt-4 space-y-3" onSubmit={(event) => void submit(event)}>
          <label className="block text-sm font-medium text-slate-700">
            Mật khẩu hiện tại
            <input
              type="password"
              autoComplete="current-password"
              autoFocus
              className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base"
              value={currentPassword}
              disabled={submitting}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Mật khẩu mới (tối thiểu 12 ký tự)
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base"
              value={newPassword}
              disabled={submitting}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Xác nhận mật khẩu mới
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base"
              value={confirmPassword}
              disabled={submitting}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              className="min-h-11 flex-1 rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 disabled:opacity-50"
              disabled={submitting}
              onClick={onClose}
            >
              Huỷ
            </button>
            <button
              type="submit"
              className="min-h-11 flex-1 rounded-lg bg-teal-700 px-3 text-sm font-semibold text-white disabled:opacity-60"
              disabled={submitting}
            >
              {submitting ? "Đang đổi…" : "Đổi mật khẩu"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
