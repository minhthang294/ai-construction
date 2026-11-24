import { SECONDARY_BUTTON } from "../lib/dailyProgressPanel";

type Props = {
  error: string | null;
  message: string | null;
  pendingCode: string | null;
  onClearPending: () => void;
};

export default function DailyProgressBanners({
  error,
  message,
  pendingCode,
  onClearPending,
}: Props) {
  return (
    <>
      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"
        >
          {message}
        </p>
      ) : null}
      {pendingCode !== null ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50 p-2 text-sm text-blue-950" role="status">
          <span>
            Đã chọn {pendingCode} từ mặt bằng. Chọn bước thi công để ghi.
          </span>
          <button type="button" className={SECONDARY_BUTTON} onClick={onClearPending}>
            Bỏ cấu kiện
          </button>
        </div>
      ) : null}
    </>
  );
}
