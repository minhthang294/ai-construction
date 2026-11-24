import type { RefObject } from "react";
import {
  canCommitBulkPreview,
  constructionStatusLabel,
  scopeLabel,
  type BulkProgressDraft,
  type ProgressPreview,
  type StageDefinition,
} from "../lib/componentProgress";
import {
  FOCUS_RING,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  type ProgressBusy,
} from "../lib/componentProgressPanel";
import { formatISODate } from "../lib/datetime";

type Props = {
  preview: ProgressPreview;
  editorDefinitions: StageDefinition[];
  draft: BulkProgressDraft;
  confirmed: boolean;
  onConfirmedChange: (checked: boolean) => void;
  busy: ProgressBusy;
  headingRef: RefObject<HTMLHeadingElement | null>;
  onEdit: () => void;
  onSave: () => void;
};

export default function ComponentProgressPreview({
  preview,
  editorDefinitions,
  draft,
  confirmed,
  onConfirmedChange,
  busy,
  headingRef,
  onEdit,
  onSave,
}: Props) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-300 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4
          ref={headingRef}
          tabIndex={-1}
          className="scroll-mt-32 text-base font-semibold text-slate-900"
        >
          Xác nhận trước khi lưu
        </h4>
        <span className="text-xs text-slate-600">
          {preview.ready_count}/{preview.count} sẵn sàng
        </span>
      </div>
      <div className="rounded-lg bg-slate-50 p-2 text-sm text-slate-700">
        <p className="break-words font-semibold">
          {
            editorDefinitions.find(
              (definition) =>
                definition.id === draft.stage_definition_id,
            )?.name
          }
        </p>
        <p className="mt-1">
          {formatISODate(draft.event_date)} ·{" "}
          {constructionStatusLabel(draft.status)}
          {draft.quantity.trim() ? ` · ${draft.quantity} ${draft.unit}` : ""}
        </p>
      </div>

      {preview.warnings.length ? (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-900"
        >
          <ul className="list-disc space-y-1 pl-5">
            {preview.warnings.map((warning) => (
              <li key={warning} className="break-words">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="max-h-72 space-y-1 overflow-auto">
        {preview.components.map((row) => {
          const chosen = row.stage_options.find(
            (stage) => stage.id === row.stage_id,
          );
          return (
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
                {chosen
                  ? `Phạm vi: ${scopeLabel(chosen.scope_kind)}`
                  : row.stage_ambiguous
                    ? "Chọn phạm vi"
                    : row.stage_available
                      ? "Có bước thi công"
                      : "Thiếu bước"}
              </span>
            </div>
          );
        })}
      </div>

      <label className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm text-slate-800">
        <input
          type="checkbox"
          className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
          checked={confirmed}
          disabled={!canCommitBulkPreview(preview) || busy !== null}
          onChange={(event) => onConfirmedChange(event.target.checked)}
        />
        <span>
          Tôi đã kiểm tra đúng {preview.components.length} cấu kiện và
          xác nhận ghi sự kiện ngày {formatISODate(draft.event_date)}.
        </span>
      </label>

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
          disabled={
            !confirmed || !canCommitBulkPreview(preview) || busy !== null
          }
          onClick={onSave}
        >
          {busy === "save"
            ? "Đang ghi tiến độ…"
            : `Lưu ${preview.components.length} sự kiện đã duyệt`}
        </button>
      </div>
    </div>
  );
}
