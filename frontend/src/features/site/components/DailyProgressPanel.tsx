import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  listComponentProgress,
  listSegments,
  listStageDefinitions,
} from "../lib/api";
import {
  constructionStatusLabel,
  scopeLabel,
  sortStagesByPosition,
  stageOptionsFor,
  todayISO,
  type ProgressRow,
  type StageDefinition,
} from "../lib/componentProgress";
import type { ComponentSegment } from "../lib/componentImport";
import { formatISODate } from "../lib/datetime";
import {
  addDailyProgressLine,
  buildDailyProgressPayload,
  canCommitDailyProgressPreview,
  changeLineStageDefinition,
  copySelectionFromPriorLine,
  createDailyProgressDraft,
  dailyProgressError,
  dailyProgressSelectedCount,
  eligibleRowsForLine,
  MAX_DAILY_PROGRESS_LINES,
  newDailyProgressIdempotencyKey,
  previewDailyProgress,
  pruneLinesToFilters,
  removeDailyProgressLine,
  saveDailyProgress,
  segmentOptionsFor,
  selectedStageForLineRow,
  stageDefinitionLabelFor,
  toggleDailyProgressComponent,
  updateDailyProgressLine,
  type DailyProgressDraft,
  type DailyProgressFilters,
  type DailyProgressPreviewResponse,
} from "../lib/dailyProgress";

type Props = { projectId: string };

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-600 focus-visible:ring-offset-2";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

const PRIMARY_BUTTON =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";

const SECONDARY_BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

const STATUS_OPTIONS = [
  { value: "IN_PROGRESS", label: "Đang thi công" },
  { value: "COMPLETED", label: "Hoàn thành" },
  { value: "BLOCKED", label: "Tạm dừng" },
] as const;
const GROUP_UNITS = ["cọc", "dầm", "vị trí", "m", "m²", "m³", "kg", "tấn", "lít", "ca"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className="inline-flex rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">
      {constructionStatusLabel(status)}
    </span>
  );
}

export default function DailyProgressPanel({ projectId }: Props) {
  const [rows, setRows] = useState<ProgressRow[]>([]);
  const [definitions, setDefinitions] = useState<StageDefinition[]>([]);
  const [segments, setSegments] = useState<ComponentSegment[]>([]);
  const [filters, setFilters] = useState<DailyProgressFilters>({
    zone: "",
    segment_id: "",
  });
  const [draft, setDraft] = useState<DailyProgressDraft>(() =>
    createDailyProgressDraft(),
  );
  const [preview, setPreview] = useState<DailyProgressPreviewResponse | null>(
    null,
  );
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"load" | "preview" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load");
    setError(null);
    try {
      const [progressRows, stageDefinitions, segmentRows] = await Promise.all([
        listComponentProgress(projectId),
        listStageDefinitions(projectId),
        listSegments(projectId),
      ]);
      setRows(progressRows);
      setDefinitions(sortStagesByPosition(stageDefinitions));
      setSegments(segmentRows);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Keep every selected id inside the current zone/segment and stage definition.
  useEffect(() => {
    if (!rows.length) return;
    setDraft((current) => ({
      ...current,
      lines: pruneLinesToFilters(current.lines, rows, filters),
    }));
  }, [rows, filters]);

  const definitionOptions = useMemo(() => {
    if (definitions.length) return definitions;
    const derived = new Map<string, StageDefinition>();
    for (const row of rows) {
      for (const stage of row.stages) {
        if (!derived.has(stage.stage_definition_id)) {
          derived.set(stage.stage_definition_id, {
            id: stage.stage_definition_id,
            type: row.type,
            code: stage.code,
            name: stage.name,
            position: stage.position,
          });
        }
      }
    }
    return sortStagesByPosition([...derived.values()]);
  }, [definitions, rows]);

  const availableWork = useMemo(() => {
    const coverage = new Map<string, { count: number; groups: Set<string> }>();
    for (const row of rows) {
      if (filters.zone && row.zone !== filters.zone) continue;
      if (filters.segment_id && row.segment_id !== filters.segment_id) continue;
      for (const id of new Set(row.stages.map((stage) => stage.stage_definition_id))) {
        const entry = coverage.get(id) ?? { count: 0, groups: new Set<string>() };
        entry.count += 1;
        if (row.design_group) entry.groups.add(row.design_group);
        coverage.set(id, entry);
      }
    }
    return definitionOptions.flatMap((definition) => {
      const entry = coverage.get(definition.id);
      if (!entry) return [];
      const scope = [...entry.groups].join(", ");
      const type = definition.type === "pile" ? "Cọc" : "Dầm";
      return [{
        id: definition.id,
        label: `${type} · ${definition.name}${scope ? ` · ${scope}` : ""} (${entry.count})`,
      }];
    });
  }, [definitionOptions, filters, rows]);

  const zones = useMemo(
    () =>
      Array.from(
        new Set([...segments.map((segment) => segment.zone), ...rows.map((row) => row.zone)]),
      )
        .filter(Boolean)
        .sort((left, right) => left.localeCompare(right, "vi")),
    [segments, rows],
  );

  const segmentOptions = useMemo(
    () => segmentOptionsFor(segments, rows, filters.zone),
    [segments, rows, filters.zone],
  );

  const eligibleByLine = useMemo(
    () =>
      draft.lines.map((line) =>
        eligibleRowsForLine(rows, line.stage_definition_id, filters),
      ),
    [draft.lines, rows, filters],
  );

  const totalSelected = dailyProgressSelectedCount(draft);
  const commitReady = canCommitDailyProgressPreview(
    preview,
    draft.lines.length,
  );
  const filtersLocked = preview !== null || totalSelected > 0;

  function invalidatePreview() {
    setPreview(null);
    setConfirmed(false);
    setIdempotencyKey(null);
  }

  function updateFilter(patch: Partial<DailyProgressFilters>) {
    setFilters((current) => {
      const next = { ...current, ...patch };
      if (
        patch.zone !== undefined &&
        patch.zone !== current.zone &&
        next.segment_id
      ) {
        const stillOffered = segmentOptionsFor(
          segments,
          rows,
          next.zone,
        ).some((segment) => segment.id === next.segment_id);
        if (!stillOffered) next.segment_id = "";
      }
      return next;
    });
    invalidatePreview();
  }

  function setLines(lines: DailyProgressDraft["lines"]) {
    setDraft((current) => ({ ...current, lines }));
    invalidatePreview();
  }

  function updateDate(eventDate: string) {
    setDraft((current) => ({ ...current, event_date: eventDate }));
    invalidatePreview();
  }

  function updateLine(
    index: number,
    patch: Partial<DailyProgressDraft["lines"][number]>,
  ) {
    setDraft((current) => ({
      ...current,
      lines: updateDailyProgressLine(current.lines, index, patch),
    }));
    invalidatePreview();
  }

  function changeDefinition(index: number, stageDefinitionId: string) {
    setDraft((current) => ({
      ...current,
      lines: changeLineStageDefinition(current.lines, index, stageDefinitionId),
    }));
    invalidatePreview();
  }

  function toggleComponent(index: number, componentId: string) {
    setDraft((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) =>
        lineIndex === index
          ? toggleDailyProgressComponent(line, componentId)
          : line,
      ),
    }));
    invalidatePreview();
  }

  function setStageChoice(index: number, componentId: string, stageId: string) {
    setDraft((current) => {
      const line = current.lines[index];
      const stageSelections = { ...line.stage_selections };
      if (stageId) stageSelections[componentId] = stageId;
      else delete stageSelections[componentId];
      return {
        ...current,
        lines: updateDailyProgressLine(current.lines, index, { stage_selections: stageSelections }),
      };
    });
    invalidatePreview();
  }

  function selectAll(index: number) {
    const eligible = eligibleByLine[index] ?? [];
    updateLine(index, {
      selected_ids: eligible.map((row) => row.id),
    });
  }

  function clearLine(index: number) {
    updateLine(index, { selected_ids: [], stage_selections: {} });
  }

  function copyPrior(index: number) {
    if (index <= 0) return;
    const eligible = eligibleByLine[index] ?? [];
    const copied = copySelectionFromPriorLine(draft.lines, index, eligible);
    updateLine(index, copied);
    setMessage(
      copied.selected_ids.length
        ? `Đã sao chép ${copied.selected_ids.length} cấu kiện từ dòng trước.`
        : "Dòng trước không có cấu kiện phù hợp với dòng này.",
    );
  }

  async function handlePreview() {
    const validation = dailyProgressError(draft, rows, filters);
    if (validation || busy) {
      setError(validation);
      return;
    }
    setBusy("preview");
    setError(null);
    setMessage(null);
    try {
      const data = await previewDailyProgress(
        projectId,
        buildDailyProgressPayload(draft),
      );
      setPreview(data);
      setConfirmed(false);
      setIdempotencyKey(newDailyProgressIdempotencyKey());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSave() {
    if (
      !preview ||
      !idempotencyKey ||
      !confirmed ||
      !commitReady ||
      busy
    ) {
      return;
    }
    setBusy("save");
    setError(null);
    try {
      const result = await saveDailyProgress(
        projectId,
        buildDailyProgressPayload(draft),
        idempotencyKey,
      );
      setMessage(`Đã ghi ${result.created} sự kiện tiến độ.`);
      setPreview(null);
      setConfirmed(false);
      setIdempotencyKey(null);
      setDraft(createDailyProgressDraft(draft.event_date));
      await load();
    } catch (err) {
      // Keep the same preview and key so an identical retry stays idempotent.
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  function editAgain() {
    invalidatePreview();
    setError(null);
  }

  return (
    <section className="mx-auto w-full max-w-3xl space-y-3">
      <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <h4 className="text-base font-semibold text-slate-900 sm:text-lg">
          Tiến độ trong ngày
        </h4>
        <p className="mt-1 text-xs text-slate-600">
          Chọn đúng bước thi công và cấu kiện có thật; xem lại rồi mới lưu.
        </p>
        <label className="mt-3 block text-xs font-medium text-slate-700">
          Ngày ghi nhận
          <input
            type="date"
            className={FIELD}
            value={draft.event_date}
            max={todayISO()}
            disabled={preview !== null || busy === "load"}
            onChange={(event) => updateDate(event.target.value)}
          />
        </label>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Khu vực
            <select
              className={FIELD}
              value={filters.zone}
              disabled={filtersLocked || busy === "load"}
              onChange={(event) => updateFilter({ zone: event.target.value })}
            >
              <option value="">Tất cả khu</option>
              {zones.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Phân đoạn
            <select
              className={FIELD}
              value={filters.segment_id}
              disabled={filtersLocked || busy === "load"}
              onChange={(event) =>
                updateFilter({ segment_id: event.target.value })
              }
            >
              <option value="">Tất cả phân đoạn</option>
              {segmentOptions.map((segment) => (
                <option key={segment.id} value={segment.id}>
                  PĐ {segment.number}
                </option>
              ))}
            </select>
          </label>
        </div>
        {busy === "load" ? (
          <p className="mt-2 text-xs text-slate-600">Đang tải dữ liệu…</p>
        ) : null}
        {!busy && !rows.length && !error ? (
          <p className="mt-2 text-sm text-slate-600">
            Chưa có cấu kiện trong công trình.
          </p>
        ) : null}
      </div>

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

      {!preview ? (
        <>
          {draft.lines.map((line, index) => {
            const eligible = eligibleByLine[index] ?? [];
            const selectedSet = new Set(line.selected_ids);
            return (
              <div
                key={index}
                className="space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h5 className="text-base font-semibold text-slate-900">
                      Dòng {index + 1}
                    </h5>
                    <p className="text-xs text-slate-600">
                      {line.selected_ids.length}/{eligible.length} cấu kiện đã chọn
                    </p>
                  </div>
                  {draft.lines.length > 1 ? (
                    <button
                      type="button"
                      className={`${SECONDARY_BUTTON} shrink-0 ${FOCUS_RING}`}
                      disabled={busy !== null}
                      onClick={() =>
                        setLines(removeDailyProgressLine(draft.lines, index))
                      }
                    >
                      Xóa dòng
                    </button>
                  ) : null}
                </div>

                <label className="block text-xs font-medium text-slate-700">
                  Bước thi công
                  <select
                    className={FIELD}
                    value={line.stage_definition_id}
                    disabled={busy === "load"}
                    onChange={(event) =>
                      changeDefinition(index, event.target.value)
                    }
                  >
                    <option value="">— Chọn bước —</option>
                    {availableWork.map((work) => (
                      <option key={work.id} value={work.id}>
                        {work.label}
                      </option>
                    ))}
                  </select>
                </label>
                {availableWork.length === 0 ? (
                  <p className="text-xs text-amber-800">
                    Chưa có công tác theo bộ lọc đang chọn.
                  </p>
                ) : null}

                {line.stage_definition_id ? (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                        disabled={busy !== null || eligible.length === 0}
                        onClick={() => selectAll(index)}
                      >
                        Chọn tất cả
                      </button>
                      <button
                        type="button"
                        className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                        disabled={busy !== null || line.selected_ids.length === 0}
                        onClick={() => clearLine(index)}
                      >
                        Bỏ chọn
                      </button>
                      {index > 0 ? (
                        <button
                          type="button"
                          className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                          disabled={busy !== null || eligible.length === 0}
                          onClick={() => copyPrior(index)}
                        >
                          Sao chép dòng trước
                        </button>
                      ) : null}
                    </div>

                    {eligible.length ? (
                      <div className="max-h-80 space-y-2 overflow-auto">
                        {eligible.map((row) => {
                          const selected = selectedSet.has(row.id);
                          const options = stageOptionsFor(
                            row,
                            line.stage_definition_id,
                          );
                          const chosen = selectedStageForLineRow(line, row);
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
                                  onChange={() => toggleComponent(index, row.id)}
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
                                      setStageChoice(
                                        index,
                                        row.id,
                                        event.target.value,
                                      )
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
                        updateLine(index, {
                          status: event.target
                            .value as DailyProgressDraft["lines"][number]["status"],
                        })
                      }
                    >
                      <option value="">— Chọn trạng thái —</option>
                      {STATUS_OPTIONS.map((option) => (
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
                          updateLine(index, {
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
                          updateLine(index, { group_unit: event.target.value })
                        }
                      >
                        <option value="">Chọn đơn vị</option>
                        {GROUP_UNITS.map((unit) => <option key={unit}>{unit}</option>)}
                      </select>
                    </label>
                  </div>
                </div>
              </div>
            );
          })}

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
              disabled={
                busy !== null || draft.lines.length >= MAX_DAILY_PROGRESS_LINES
              }
              onClick={() => setLines(addDailyProgressLine(draft.lines))}
            >
              Thêm công tác
            </button>
            <button
              type="button"
              className={`${PRIMARY_BUTTON} flex-1 ${FOCUS_RING}`}
              disabled={busy !== null}
              onClick={() => void handlePreview()}
            >
              {busy === "preview"
                ? "Đang kiểm tra…"
                : `Xem lại ${totalSelected} lượt cập nhật`}
            </button>
          </div>
        </>
      ) : (
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
              const lineIndex = linePreview.line_index ?? index;
              const line = draft.lines[lineIndex];
              const group = line
                ? stageDefinitionLabelFor(
                    definitionOptions,
                    line.stage_definition_id,
                  )
                : "Dòng không còn trong biểu mẫu";
              const groupText =
                linePreview.group_quantity !== null
                  ? `${linePreview.group_quantity} ${linePreview.group_unit ?? ""}`.trim()
                  : linePreview.group_unit ?? "";
              return (
                <section
                  key={lineIndex}
                  className="min-w-0 rounded-lg border border-slate-200 p-2"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-1">
                    <h5 className="break-words text-sm font-semibold text-slate-900">
                      Dòng {lineIndex + 1} · {group}
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
                    {linePreview.components.map((row) => {
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
                              ? `${scopeLabel(chosen.scope_kind)} · ${chosen.name}`
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
                </section>
              );
            })}
          </div>

          {preview.lines.length !== draft.lines.length ? (
            <p className="text-xs text-red-800">
              Máy chủ trả về {preview.lines.length} dòng, không khớp biểu mẫu.
              Quay lại và xem lại.
            </p>
          ) : null}

          <label className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm text-slate-800">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
              checked={confirmed}
              disabled={!commitReady || busy !== null}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              Tôi đã kiểm tra đúng {draft.lines.length} dòng, {totalSelected}{" "}
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
              onClick={editAgain}
            >
              Sửa thông tin
            </button>
            <button
              type="button"
              className={`${PRIMARY_BUTTON} flex-1 ${FOCUS_RING}`}
              disabled={!confirmed || !commitReady || busy !== null}
              onClick={() => void handleSave()}
            >
              {busy === "save"
                ? "Đang ghi tiến độ…"
                : `Lưu ${totalSelected} lượt cập nhật`}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
