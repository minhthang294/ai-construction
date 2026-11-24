import {
  FOCUS_RING,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  type DailyProgressBusy,
} from "../lib/dailyProgressPanel";

type Props = {
  busy: DailyProgressBusy;
  selectedCount: number;
  addDisabled: boolean;
  onAdd: () => void;
  onPreview: () => void;
};

export default function DailyProgressFooter({
  busy,
  selectedCount,
  addDisabled,
  onAdd,
  onPreview,
}: Props) {
  return (
    <div className="sticky bottom-[calc(3.75rem+env(safe-area-inset-bottom))] z-20 -mx-1 flex flex-row items-stretch gap-2 border-t border-slate-200 bg-white/95 p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-6px_16px_rgba(15,23,42,0.08)] backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none sm:backdrop-blur-none">
      <button
        type="button"
        className={`${SECONDARY_BUTTON} shrink-0 ${FOCUS_RING}`}
        disabled={addDisabled}
        onClick={onAdd}
      >
        Thêm công tác
      </button>
      <button
        type="button"
        className={`${PRIMARY_BUTTON} flex-1 ${FOCUS_RING}`}
        disabled={busy !== null}
        onClick={onPreview}
      >
        {busy === "preview"
          ? "Đang kiểm tra…"
          : `Xem lại ${selectedCount} lượt cập nhật`}
      </button>
    </div>
  );
}
