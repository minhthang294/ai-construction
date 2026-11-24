import {
  acceptanceStatusLabel,
  constructionStatusLabel,
  scopeLabel,
  sortStagesByPosition,
  type ProgressRow,
} from "../lib/componentProgress";
import {
  FOCUS_RING,
  acceptanceChipClass,
  statusChipClass,
} from "../lib/componentProgressPanel";
import { formatISODate } from "../lib/datetime";
import BatchZoneBadge from "./BatchZoneBadge";
import ProgressHistoryPanel from "./ProgressHistoryPanel";

function StatusChip({ status }: { status: string }) {
  return (
    <span className={statusChipClass(status)}>
      {constructionStatusLabel(status)}
    </span>
  );
}

function AcceptanceChip({ status }: { status: string }) {
  return (
    <span className={acceptanceChipClass(status)}>
      {acceptanceStatusLabel(status)}
    </span>
  );
}

type ProgressCardProps = {
  row: ProgressRow;
  projectId: string;
  primaryZone?: string | null;
  onChanged: () => void;
  selectionMode: boolean;
  selected: boolean;
  onToggle: () => void;
  onOpen: () => void;
};

export default function ProgressCard({
  row,
  projectId,
  primaryZone,
  onChanged,
  selectionMode,
  selected,
  onToggle,
  onOpen,
}: ProgressCardProps) {
  const event = row.construction_event;
  return (
    <article
      className={`min-w-0 rounded-xl border bg-white p-3 shadow-sm ${
        selected ? "border-slate-500 ring-1 ring-slate-400" : "border-slate-200"
      }`}
    >
      {selectionMode ? (
        <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-1 text-sm font-medium text-slate-800">
          <input
            type="checkbox"
            className="h-5 w-5 shrink-0 accent-slate-700"
            checked={selected}
            onChange={onToggle}
            aria-label={`Chọn ${row.canonical_code}`}
          />
          <span className="min-w-0 break-words">
            {selected ? "Đã chọn" : "Chọn cấu kiện"}
          </span>
        </label>
      ) : null}

      <div className="mt-1 flex min-w-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words font-mono text-base font-semibold text-slate-900">
            {row.canonical_code}
          </p>
          {row.raw_code !== row.canonical_code ? (
            <p className="break-words font-mono text-xs text-slate-600">
              Mã gốc: {row.raw_code}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          {row.scopes.includes("ADDITIONAL_SCOPE") ? (
            <span className="rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-xs text-purple-900">
              Phát sinh
            </span>
          ) : null}
          {row.verification !== "VERIFIED" ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-900">
              Chờ duyệt
            </span>
          ) : null}
        </div>
      </div>

      <p className="mt-1 break-words text-sm text-slate-600">
        {row.zone} · PĐ {row.segment_number} ·{" "}
        {row.type === "pile" ? "Cọc" : "Dầm"}
        {row.design_group ? ` · ${row.design_group}` : ""}
      </p>
      <div className="mt-1">
        <BatchZoneBadge
          zone={row.zone}
          segmentNumber={row.segment_number}
          primaryZone={primaryZone}
        />
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <p className="font-medium text-slate-600">Thi công</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <StatusChip status={row.construction_status} />
            {event ? (
              <span className="break-words text-slate-600">
                {event.stage_name || event.stage_code || "—"} ·{" "}
                {formatISODate(event.event_date)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <p className="font-medium text-slate-600">Nghiệm thu</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <AcceptanceChip status={row.acceptance_status} />
          </div>
        </div>
      </div>

      {row.stages.length ? (
        <details className="mt-2 rounded-lg border border-slate-200">
          <summary
            className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-2 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
          >
            <span>Bước thi công ({row.stages.length})</span>
            <span aria-hidden="true" className="text-slate-500">
              ⌄
            </span>
          </summary>
          <ul className="space-y-1 border-t border-slate-200 p-2 text-xs text-slate-600">
            {sortStagesByPosition(row.stages).map((stage) => {
              const source = row.stages.find(
                (item) => item.id === stage.inferred_from_stage_id,
              );
              return (
                <li
                  key={stage.id}
                  className="flex min-w-0 flex-wrap items-center gap-1 break-words"
                >
                  <span className="min-w-0 break-words">{stage.name}</span>
                  {stage.scope_kind ? (
                    <span>· {scopeLabel(stage.scope_kind)}</span>
                  ) : null}
                  <StatusChip status={stage.status} />
                  {stage.inference_conflict ? (
                    <span className="text-amber-800">
                      Cần đối chiếu với bước sau
                    </span>
                  ) : stage.inferred_from_stage_id ? (
                    <span className="text-slate-700">
                      Suy ra từ bước sau
                      {source ? ` · ${source.name}` : ""}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : (
        <p className="mt-2 text-xs text-amber-800">Chưa gắn bước thi công.</p>
      )}

      {!selectionMode ? (
        <button
          type="button"
          className={`mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 ${FOCUS_RING}`}
          onClick={onOpen}
        >
          Ghi tiến độ
        </button>
      ) : null}
      <ProgressHistoryPanel
        projectId={projectId}
        componentId={row.id}
        onChanged={onChanged}
      />
    </article>
  );
}
