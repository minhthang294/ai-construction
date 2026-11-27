import {
  constructionStatusLabel,
  scopeLabel,
  type ProgressRow,
} from "../lib/componentProgress";
import {
  selectedStageForLineRow,
  type DailyProgressLineDraft,
} from "../lib/dailyProgress";
import {
  stageOptionsForMainWork,
  type MainWork,
} from "../lib/mainWorks";
import {
  DAILY_STATUS_OPTIONS,
  FIELD,
  FOCUS_RING,
  GROUP_UNITS,
  SECONDARY_BUTTON,
  lineSelectionSummary,
  statusChipClass,
  type AvailableWork,
  type DailyProgressBusy,
} from "../lib/dailyProgressPanel";
import BatchZoneBadge from "./BatchZoneBadge";
import DrawingMapPanel from "./DrawingMapPanel";
import QuickCodeEntry from "./QuickCodeEntry";

function StatusChip({ status }: { status: string }) {
  return (
    <span className={statusChipClass(status)}>
      {constructionStatusLabel(status)}
    </span>
  );
}

type Props = {
  projectId: string;
  batchId?: string | null;
  primaryZone?: string | null;
  index: number;
  line: DailyProgressLineDraft;
  rows: ProgressRow[];
  eligible: ProgressRow[];
  works: MainWork[];
  availableWork: AvailableWork[];
  lineCount: number;
  busy: DailyProgressBusy;
  expanded: boolean;
  mapOpen: boolean;
  listOpen: boolean;
  onToggleExpanded: () => void;
  onRemove: () => void;
  onChangeDefinition: (mainWorkKey: string) => void;
  onUpdateLine: (patch: Partial<DailyProgressLineDraft>) => void;
  onToggleComponent: (componentId: string) => void;
  onStageChoice: (componentId: string, stageId: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
  onCopyPrior: () => void;
  onToggleMap: () => void;
  onToggleList: () => void;
};

export default function DailyProgressLineCard({
  projectId,
  batchId,
  primaryZone,
  index,
  line,
  rows,
  eligible,
  works,
  availableWork,
  lineCount,
  busy,
  expanded,
  mapOpen,
  listOpen,
  onToggleExpanded,
  onRemove,
  onChangeDefinition,
  onUpdateLine,
  onToggleComponent,
  onStageChoice,
  onSelectAll,
  onClear,
  onCopyPrior,
  onToggleMap,
  onToggleList,
}: Props) {
  const selectedSet = new Set(line.selected_ids);
  const work = works.find((item) => item.key === line.main_work_key) ?? null;
  const workLabel =
    availableWork.find((item) => item.key === line.main_work_key)?.label ??
    (work ? `${work.component_type === "pile" ? "Cọc" : "Dầm"} · ${work.label}` : "");
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className={`min-h-11 min-w-0 flex-1 rounded-lg text-left ${FOCUS_RING}`}
          aria-expanded={expanded}
          onClick={onToggleExpanded}
        >
          <span className="block truncate text-sm font-semibold text-slate-900">
            {index + 1}. {workLabel || "Chọn công tác"}
          </span>
          <span className="block truncate text-xs text-slate-600">
            {lineSelectionSummary(line, eligible.length, rows)}
          </span>
        </button>
        {lineCount > 1 ? (
          <button
            type="button"
            className={`${SECONDARY_BUTTON} shrink-0 ${FOCUS_RING}`}
            disabled={busy !== null}
            onClick={onRemove}
          >
            Xóa dòng
          </button>
        ) : null}
      </div>

      {expanded ? (
      <div className="mt-3 space-y-3">

      <label className="block text-xs font-medium text-slate-700">
        Công tác
        <select
          className={FIELD}
          value={line.main_work_key}
          disabled={busy === "load"}
          onChange={(event) => onChangeDefinition(event.target.value)}
        >
          <option value="">— Chọn công tác —</option>
          {(["pile", "beam"] as const).map((type) => {
            const items = availableWork.filter((item) => item.type === type);
            if (!items.length) return null;
            return (
              <optgroup
                key={type}
                label={type === "pile" ? "Cọc" : "Dầm"}
              >
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
      {availableWork.length === 0 ? (
        <p className="text-xs text-amber-800">
          Chưa có công tác theo bộ lọc đang chọn.
        </p>
      ) : null}

      {line.main_work_key ? (
        <QuickCodeEntry
          rows={eligible}
          selectedIds={line.selected_ids}
          disabled={busy !== null}
          onConfirm={(ids) =>
            onUpdateLine({
              selected_ids: Array.from(
                new Set([...line.selected_ids, ...ids]),
              ),
            })
          }
        />
      ) : null}

      <button
        type="button"
        className={`${SECONDARY_BUTTON} w-full ${FOCUS_RING}`}
        disabled={busy !== null || (!line.main_work_key && !mapOpen)}
        onClick={onToggleMap}
      >
        {mapOpen ? "Ẩn sơ đồ" : line.main_work_key ? "Chọn cấu kiện trên sơ đồ" : "Chọn công tác trước"}
      </button>
      {mapOpen ? (
        <DrawingMapPanel
          projectId={projectId}
          batchId={batchId}
          selection={{
            selectedIds: line.selected_ids,
            selectableIds: eligible.map((row) => row.id),
            disabled: busy !== null,
            onToggle: onToggleComponent,
          }}
        />
      ) : null}

      {line.main_work_key ? (
        <>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
              disabled={busy !== null || eligible.length === 0}
              onClick={onSelectAll}
            >
              Chọn tất cả
            </button>
            <button
              type="button"
              className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
              disabled={busy !== null || line.selected_ids.length === 0}
              onClick={onClear}
            >
              Bỏ chọn
            </button>
            {index > 0 ? (
              <button
                type="button"
                className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                disabled={busy !== null || eligible.length === 0}
                onClick={onCopyPrior}
              >
                Sao chép dòng trước
              </button>
            ) : null}
          </div>

          <button
            type="button"
            className={`${SECONDARY_BUTTON} w-full ${FOCUS_RING}`}
            disabled={busy !== null || eligible.length === 0}
            aria-expanded={listOpen}
            onClick={onToggleList}
          >
            {listOpen ? "Ẩn danh sách" : `Chọn theo danh sách · ${line.selected_ids.length}/${eligible.length}`}
          </button>

          {eligible.length && listOpen ? (
            <div className="max-h-80 space-y-2 overflow-auto">
              {eligible.map((row) => {
                const selected = selectedSet.has(row.id);
                const options = work
                  ? stageOptionsForMainWork(row, work)
                  : [];
                const chosen = selectedStageForLineRow(line, row, work);
                return (
                  <div
                    key={row.id}
                    className={`min-w-0 rounded-lg border p-2 ${
                      selected
                        ? "border-slate-500 bg-slate-50 ring-1 ring-slate-300"
                        : "border-slate-200"
                    }`}
                  >
                    <label className="flex min-h-11 cursor-pointer items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
                        checked={selected}
                        disabled={busy !== null}
                        onChange={() => onToggleComponent(row.id)}
                        aria-label={`Chọn ${row.canonical_code}`}
                      />
                      <span className="min-w-0">
                        <span className="block break-words font-mono text-sm font-semibold text-slate-900">
                          {row.canonical_code}
                        </span>
                        <span className="block break-words text-xs text-slate-600">
                          {row.zone} · PĐ {row.segment_number}
                          {row.design_group
                            ? ` · ${row.design_group}`
                            : ""}
                        </span>
                        <span className="mt-1 block">
                          <BatchZoneBadge
                            zone={row.zone}
                            segmentNumber={row.segment_number}
                            primaryZone={primaryZone}
                          />
                        </span>
                        <span className="mt-1 flex flex-wrap items-center gap-1 text-xs text-slate-700">
                          <StatusChip status={row.construction_status} />
                          {chosen ? (
                            <span className="break-words">
                              {scopeLabel(chosen.scope_kind)} ·{" "}
                              {chosen.name}
                            </span>
                          ) : options.length > 1 ? (
                            <span className="text-amber-800">
                              Cần chọn bước cụ thể
                            </span>
                          ) : null}
                        </span>
                      </span>
                    </label>
                    {selected && options.length > 1 ? (
                      <label className="mt-2 block pl-7 text-xs font-medium text-slate-700">
                        Bước cụ thể
                        <select
                          className={FIELD}
                          value={line.stage_selections[row.id] ?? ""}
                          disabled={busy !== null}
                          onChange={(event) =>
                            onStageChoice(row.id, event.target.value)
                          }
                        >
                          <option value="">— Chọn bước —</option>
                          {options.map((stage) => (
                            <option key={stage.id} value={stage.id}>
                              {scopeLabel(stage.scope_kind)} ·{" "}
                              {stage.name} ·{" "}
                              {constructionStatusLabel(stage.status)}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm text-slate-600">
              Không có cấu kiện gắn bước này trong khu/phân đoạn đã
              chọn.
            </p>
          )}
        </>
      ) : null}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Trạng thái thi công
          <select
            className={FIELD}
            value={line.status}
            disabled={busy !== null}
            onChange={(event) =>
              onUpdateLine({
                status: event.target
                  .value as DailyProgressLineDraft["status"],
              })
            }
          >
            <option value="">— Chọn trạng thái —</option>
            {DAILY_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Khối lượng nhóm
            <input
              inputMode="decimal"
              className={FIELD}
              value={line.group_quantity}
              placeholder="Tùy chọn"
              disabled={busy !== null}
              onChange={(event) =>
                onUpdateLine({
                  group_quantity: event.target.value,
                })
              }
            />
          </label>
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Đơn vị
            <select
              className={FIELD}
              value={line.group_unit}
              disabled={busy !== null}
              onChange={(event) =>
                onUpdateLine({ group_unit: event.target.value })
              }
            >
              <option value="">Chọn đơn vị</option>
              {GROUP_UNITS.map((unit) => <option key={unit}>{unit}</option>)}
            </select>
          </label>
        </div>
      </div>
      </div>
      ) : null}
    </div>
  );
}
