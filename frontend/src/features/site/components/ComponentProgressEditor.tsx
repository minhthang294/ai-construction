import {
  constructionStatusLabel,
  scopeLabel,
  type BulkProgressDraft,
  type DesignQuantityGroup,
  type ProgressRow,
} from "../lib/componentProgress";
import { stageOptionsForMainWork, type MainWork } from "../lib/mainWorks";
import {
  FIELD,
  FOCUS_RING,
  PRIMARY_BUTTON,
  type ProgressBusy,
} from "../lib/componentProgressPanel";

function DesignQuantityList({
  groups,
  showWork,
  showCodes,
}: {
  groups: DesignQuantityGroup[];
  showWork?: boolean;
  showCodes?: boolean;
}) {
  return (
    <ul className="divide-y divide-slate-200">
      {groups.flatMap(({ items }) => items).map((item) => (
        <li key={item.key} className="space-y-1 py-2">
          {showWork ? (
            <p className="break-words text-sm text-slate-800">
              {item.stageNames.join(" · ")}
            </p>
          ) : null}
          <p className="break-words text-sm font-semibold text-slate-900">
            {item.quantityLabel}
          </p>
          {item.scope !== "COMPONENT" ? (
            <p className="break-words text-xs font-medium text-slate-800">
              {item.scope === "SHARED" ? "Dùng chung" : "Tổng theo nhóm"} ·{" "}
              {item.scopeLabel}
            </p>
          ) : null}
          {showCodes ? (
            <p className="break-words text-xs text-slate-700">
              {item.componentCodes.join(", ")}
            </p>
          ) : null}
          {item.drawing || item.page ? (
            <p className="text-xs text-slate-700">
              {[item.drawing, item.page ? `PDF trang ${item.page}` : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
          ) : null}
          {item.note ? (
            <p className="break-words text-xs text-slate-700">{item.note}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

type Props = {
  selectedRows: ProgressRow[];
  draft: BulkProgressDraft;
  updateDraft: (patch: Partial<BulkProgressDraft>) => void;
  works: MainWork[];
  work: MainWork | null;
  designStatus: "idle" | "loading" | "ready" | "error";
  selectedQuantityGroups: DesignQuantityGroup[];
  allQuantityGroups: DesignQuantityGroup[];
  missingStageChoices: number;
  ambiguousSelectedRows: ProgressRow[];
  stageSelections: Record<string, string>;
  updateStageSelection: (componentId: string, stageId: string) => void;
  busy: ProgressBusy;
  onPreview: () => void;
};

export default function ComponentProgressEditor({
  selectedRows,
  draft,
  updateDraft,
  works,
  work,
  designStatus,
  selectedQuantityGroups,
  allQuantityGroups,
  missingStageChoices,
  ambiguousSelectedRows,
  stageSelections,
  updateStageSelection,
  busy,
  onPreview,
}: Props) {
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <label className="block text-xs font-medium text-slate-700">
        Công tác
        <select
          className={FIELD}
          value={draft.main_work_key}
          onChange={(event) =>
            updateDraft({ main_work_key: event.target.value })
          }
        >
          <option value="">— Chọn công tác —</option>
          {(["pile", "beam"] as const).map((type) => {
            const items = works.filter((item) => item.component_type === type);
            if (!items.length) return null;
            return (
              <optgroup key={type} label={type === "pile" ? "Cọc" : "Dầm"}>
                {items.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.label}
                  </option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </label>
      {works.length === 0 ? (
        <p className="text-xs text-amber-800">
          Chưa tải được danh mục công tác.
        </p>
      ) : null}

      <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2" aria-live="polite">
        <h5 className="text-sm font-semibold text-slate-900">
          Khối lượng thiết kế
        </h5>
        {designStatus === "loading" ? (
          <p className="mt-1 text-sm text-slate-700">Đang tải số liệu…</p>
        ) : designStatus === "error" ? (
          <p className="mt-1 text-sm text-slate-700">
            Chưa tải được số liệu thiết kế.
          </p>
        ) : selectedQuantityGroups.length ? (
          <DesignQuantityList
            groups={selectedQuantityGroups}
            showCodes={selectedRows.length > 1}
          />
        ) : (
          <p className="mt-1 text-sm text-slate-700">
            {!draft.main_work_key && allQuantityGroups.length
              ? "Chọn công tác để xem khối lượng."
              : draft.main_work_key && missingStageChoices
                ? "Chọn phạm vi để xem khối lượng."
                : "Chưa có khối lượng thiết kế cho lựa chọn này."}
          </p>
        )}
        {allQuantityGroups.length ? (
          <details className="mt-1 border-t border-slate-200">
            <summary
              className={`min-h-11 py-3 text-sm font-medium text-slate-800 ${FOCUS_RING}`}
            >
              Xem khối lượng các bước
            </summary>
            <DesignQuantityList groups={allQuantityGroups} showWork />
          </details>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Ngày ghi nhận
          <input
            type="date"
            className={FIELD}
            value={draft.event_date}
            onChange={(event) =>
              updateDraft({ event_date: event.target.value })
            }
          />
        </label>
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Trạng thái
          <select
            className={FIELD}
            value={draft.status}
            onChange={(event) =>
              updateDraft({
                status: event.target.value as BulkProgressDraft["status"],
              })
            }
          >
            <option value="">— Chọn trạng thái —</option>
            <option value="IN_PROGRESS">Đang thi công</option>
            <option value="COMPLETED">Hoàn thành</option>
            <option value="BLOCKED">Tạm dừng</option>
          </select>
        </label>
      </div>

      <details className="rounded-lg border border-slate-200">
        <summary
          className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-2 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
        >
          <span>Thêm khối lượng, đơn vị, ghi chú</span>
          <span aria-hidden="true" className="text-slate-500">
            ⌄
          </span>
        </summary>
        <div className="grid grid-cols-1 gap-2 border-t border-slate-200 p-2 sm:grid-cols-2">
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Khối lượng thực hiện
            <input
              inputMode="decimal"
              className={FIELD}
              value={draft.quantity}
              placeholder="Để trống nếu chưa rõ"
              onChange={(event) =>
                updateDraft({ quantity: event.target.value })
              }
            />
          </label>
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Đơn vị
            <input
              maxLength={30}
              className={FIELD}
              value={draft.unit}
              onChange={(event) => updateDraft({ unit: event.target.value })}
            />
          </label>
          <label className="min-w-0 text-xs font-medium text-slate-700 sm:col-span-2">
            Ghi chú
            <textarea
              maxLength={2000}
              rows={2}
              className={FIELD}
              value={draft.note}
              onChange={(event) => updateDraft({ note: event.target.value })}
            />
          </label>
        </div>
      </details>

      {ambiguousSelectedRows.length ? (
        <div className="rounded-lg border border-slate-300 bg-slate-50 p-2 text-xs text-slate-800">
          <p className="font-medium">
            Chọn phạm vi cho {ambiguousSelectedRows.length} cấu kiện
          </p>
          <p className="mt-1 text-slate-600">
            Cùng một bước có ở nhiều phạm vi sửa chữa; máy chủ không tự
            chọn.
          </p>
          <div className="mt-2 space-y-2">
            {ambiguousSelectedRows.map((row) => (
              <label
                key={row.id}
                className="grid gap-1 sm:grid-cols-[9rem_1fr] sm:items-center"
              >
                <span className="min-w-0 break-words font-mono font-semibold">
                  {row.canonical_code}
                </span>
                <select
                  className={FIELD}
                  value={stageSelections[row.id] ?? ""}
                  onChange={(event) =>
                    updateStageSelection(row.id, event.target.value)
                  }
                >
                  <option value="">— Chọn phạm vi —</option>
                  {(work ? stageOptionsForMainWork(row, work) : []).map(
                    (stage) => (
                      <option key={stage.id} value={stage.id}>
                        {scopeLabel(stage.scope_kind)} · {stage.name} ·{" "}
                        {constructionStatusLabel(stage.status)}
                      </option>
                    ),
                  )}
                </select>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      <button
        type="button"
        className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
        disabled={busy !== null}
        onClick={onPreview}
      >
        {busy === "preview" ? "Đang kiểm tra…" : "Xem lại trước khi lưu"}
      </button>
    </div>
  );
}
