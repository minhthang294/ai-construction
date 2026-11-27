import { constructionStatusLabel, type StageDefinition } from "../lib/componentProgress";
import { formatISODate } from "../lib/datetime";
import type {
  DailyProgressDraft,
  DailyProgressPreviewResponse,
} from "../lib/dailyProgress";
import {
  FOCUS_RING,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  previewGroupText,
  previewLineLabel,
  previewStageText,
  type DailyProgressBusy,
} from "../lib/dailyProgressPanel";

type Props = {
  draft: DailyProgressDraft;
  preview: DailyProgressPreviewResponse;
  /** Draft line index for each preview line (one draft line may split by definition). */
  origins: number[];
  definitionOptions: StageDefinition[];
  confirmed: boolean;
  commitReady: boolean;
  busy: DailyProgressBusy;
  totalSelected: number;
  onConfirmedChange: (confirmed: boolean) => void;
  onEdit: () => void;
  onSave: () => void;
};

export default function DailyProgressPreview({
  draft,
  preview,
  origins,
  definitionOptions,
  confirmed,
  commitReady,
  busy,
  totalSelected,
  onConfirmedChange,
  onEdit,
  onSave,
}: Props) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-300 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4
          tabIndex={-1}
          className="scroll-mt-32 text-base font-semibold text-slate-900"
        >
          Xem lại trước khi lưu
        </h4>
        <span className="text-xs text-slate-600">
          {formatISODate(draft.event_date)} · {draft.lines.length} dòng ·{" "}
          {totalSelected} lượt cập nhật
        </span>
      </div>

      {preview.warnings.length ? (
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950"
        >
          <ul className="list-disc space-y-1 pl-5">
            {preview.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`} className="break-words">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="space-y-2">
        {preview.lines.map((linePreview, index) => {
          const lineIndex = origins[index] ?? index;
          const line = draft.lines[lineIndex];
          const groupLabel = previewLineLabel(
            linePreview,
            definitionOptions,
            line,
          );
          const groupText = previewGroupText(linePreview);
          return (
            <section
              key={index}
              className="min-w-0 rounded-lg border border-slate-200 p-2"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-1">
                <h5 className="break-words text-sm font-semibold text-slate-900">
                  Dòng {lineIndex + 1} · {groupLabel}
                </h5>
                <span className="text-xs text-slate-600">
                  {linePreview.ready_count}/{linePreview.count} sẵn sàng
                </span>
              </div>
              {line ? (
                <p className="mt-1 text-xs text-slate-600">
                  {constructionStatusLabel(line.status)}
                  {groupText ? ` · ${groupText}` : ""}
                </p>
              ) : null}
              {linePreview.warnings.length ? (
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-amber-900">
                  {linePreview.warnings.map((warning, warningIndex) => (
                    <li
                      key={`${warning}-${warningIndex}`}
                      className="break-words"
                    >
                      {warning}
                    </li>
                  ))}
                </ul>
              ) : null}
              <div className="mt-2 max-h-64 space-y-1 overflow-auto">
                {linePreview.components.map((row) => (
                  <div
                    key={row.id}
                    className="flex min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-100 p-2 text-xs"
                  >
                    <span className="break-words font-mono font-semibold text-slate-900">
                      {row.canonical_code}
                    </span>
                    <span className="break-words text-slate-600">
                      {row.zone} · PĐ {row.segment_number}
                    </span>
                    <span
                      className={
                        row.stage_available
                          ? "break-words text-emerald-800"
                          : "break-words text-red-800"
                      }
                    >
                      {previewStageText(row)}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>

      {preview.lines.length !== origins.length ? (
        <p className="text-xs text-red-800">
          Máy chủ trả về {preview.lines.length} đầu việc, không khớp biểu mẫu.
          Quay lại và xem lại.
        </p>
      ) : null}

      <label className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm text-slate-800">
        <input
          type="checkbox"
          className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
          checked={confirmed}
          disabled={!commitReady || busy !== null}
          onChange={(event) => onConfirmedChange(event.target.checked)}
        />
        <span>
          Tôi đã kiểm tra đúng {preview.lines.length} đầu việc, {totalSelected}{" "}
          lượt cập nhật và xác nhận ghi ngày{" "}
          {formatISODate(draft.event_date)}.
        </span>
      </label>

      {!commitReady ? (
        <p className="text-xs text-amber-900">
          Có dòng chưa sẵn sàng. Quay lại chỉnh lựa chọn rồi xem lại.
        </p>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
          disabled={busy !== null}
          onClick={onEdit}
        >
          Sửa thông tin
        </button>
        <button
          type="button"
          className={`${PRIMARY_BUTTON} flex-1 ${FOCUS_RING}`}
          disabled={!confirmed || !commitReady || busy !== null}
          onClick={onSave}
        >
          {busy === "save"
            ? "Đang ghi tiến độ…"
            : `Lưu ${totalSelected} lượt cập nhật`}
        </button>
      </div>
    </div>
  );
}
