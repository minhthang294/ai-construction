import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listComponentProgress,
  listSegments,
  listStageDefinitions,
} from "../lib/api";
import {
  sortStagesByPosition,
  todayISO,
  type ProgressRow,
  type StageDefinition,
} from "../lib/componentProgress";
import { errorMessage } from "../lib/componentProgressPanel";
import type { ComponentSegment } from "../lib/componentImport";
import DailyProgressBanners from "./DailyProgressBanners";
import DailyProgressFooter from "./DailyProgressFooter";
import DailyProgressHeader from "./DailyProgressHeader";
import DailyProgressLineCard from "./DailyProgressLineCard";
import DailyProgressPreview from "./DailyProgressPreview";
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
  toggleDailyProgressComponent,
  updateDailyProgressLine,
  type DailyProgressDraft,
  type DailyProgressFilters,
  type DailyProgressPreviewResponse,
} from "../lib/dailyProgress";
import {
  availableWorkFor,
  definitionOptionsFor,
  zonesFor,
  type DailyProgressBusy,
} from "../lib/dailyProgressPanel";

type Props = {
  projectId: string;
  batchId?: string | null;
  primaryZone?: string | null;
  initialComponentId?: string | null;
  initialStageDefinitionId?: string | null;
  onInitialComponentHandled?: () => void;
  onOpenPaste?: () => void;
};

export default function DailyProgressPanel({ projectId, batchId, primaryZone, initialComponentId, initialStageDefinitionId, onInitialComponentHandled, onOpenPaste }: Props) {
  const [rows, setRows] = useState<ProgressRow[]>([]);
  const [rowsLoaded, setRowsLoaded] = useState(false);
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
  const [busy, setBusy] = useState<DailyProgressBusy>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pendingComponentId, setPendingComponentId] = useState<string | null>(null);
  const [mapLineIndex, setMapLineIndex] = useState<number | null>(null);
  const [activeLineIndex, setActiveLineIndex] = useState(0);
  const [listLineIndex, setListLineIndex] = useState<number | null>(null);

  const load = useCallback(async () => {
    setBusy("load");
    setError(null);
    try {
      const [progressRows, stageDefinitions, segmentRows] = await Promise.all([
        listComponentProgress(projectId, undefined, batchId),
        listStageDefinitions(projectId),
        listSegments(projectId),
      ]);
      setRows(progressRows);
      setRowsLoaded(true);
      setDefinitions(sortStagesByPosition(stageDefinitions));
      setSegments(segmentRows);
    } catch (err) {
      setError(errorMessage(err));
      setRowsLoaded(true);
    } finally {
      setBusy(null);
    }
  }, [projectId, batchId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!initialComponentId || !rowsLoaded) return;
    const row = rows.find((item) => item.id === initialComponentId);
    if (!row) {
      setError("Không tìm thấy cấu kiện vừa chọn trên mặt bằng trong danh mục tiến độ.");
    } else {
      setFilters({ zone: row.zone, segment_id: row.segment_id });
      setPendingComponentId(row.id);
      const currentStage = initialStageDefinitionId
        ? row.stages.find((stage) => stage.stage_definition_id === initialStageDefinitionId)
        : null;
      if (currentStage) {
        setDraft((current) => ({
          ...current,
          lines: updateDailyProgressLine(current.lines, 0, {
            stage_definition_id: currentStage.stage_definition_id,
          }),
        }));
        setMessage(`Đã chọn ${row.canonical_code} và bước đang làm “${currentStage.name}” từ mặt bằng.`);
      } else {
        setMessage(`Đã chọn ${row.canonical_code} từ mặt bằng. Chọn bước thi công để ghi tiến độ.`);
      }
    }
    onInitialComponentHandled?.();
  }, [initialComponentId, initialStageDefinitionId, onInitialComponentHandled, rows, rowsLoaded]);

  // Keep every selected id inside the current zone/segment and stage definition.
  useEffect(() => {
    if (!rows.length) return;
    setDraft((current) => ({
      ...current,
      lines: pruneLinesToFilters(current.lines, rows, filters),
    }));
  }, [rows, filters]);

  const definitionOptions = useMemo(
    () => definitionOptionsFor(definitions, rows),
    [definitions, rows],
  );

  const availableWork = useMemo(
    () => availableWorkFor(rows, filters, definitionOptions),
    [definitionOptions, filters, rows],
  );

  const zones = useMemo(() => zonesFor(segments, rows), [segments, rows]);

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

  useEffect(() => {
    if (!pendingComponentId) return;
    const lineIndex = draft.lines.findIndex((line) =>
      eligibleRowsForLine(rows, line.stage_definition_id, filters)
        .some((row) => row.id === pendingComponentId),
    );
    if (lineIndex < 0) return;
    setActiveLineIndex(lineIndex);
    const target = rows.find((row) => row.id === pendingComponentId);
    setDraft((current) => {
      const line = current.lines[lineIndex];
      if (!line || line.selected_ids.includes(pendingComponentId)) return current;
      return {
        ...current,
        lines: updateDailyProgressLine(current.lines, lineIndex, {
          selected_ids: [...line.selected_ids, pendingComponentId],
        }),
      };
    });
    if (target) setMessage(`Đã thêm ${target.canonical_code} vào dòng ${lineIndex + 1}. Kiểm tra bước cụ thể trước khi xem lại.`);
    setPendingComponentId(null);
  }, [draft.lines, filters, pendingComponentId, rows]);

  const totalSelected = dailyProgressSelectedCount(draft);
  const commitReady = canCommitDailyProgressPreview(
    preview,
    draft.lines.length,
  );
  const filtersLocked = preview !== null || totalSelected > 0;
  const pendingCode = pendingComponentId
    ? rows.find((row) => row.id === pendingComponentId)?.canonical_code ?? "cấu kiện"
    : null;

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

  function removeLine(index: number) {
    setLines(removeDailyProgressLine(draft.lines, index));
    setMapLineIndex(null);
  }

  function addLine() {
    setLines(addDailyProgressLine(draft.lines));
    setActiveLineIndex(draft.lines.length);
  }

  async function handlePreview() {
    const validation = dailyProgressError(draft, rows, filters);
    if (validation || busy) {
      setError(validation);
      return;
    }
    setBusy("preview");
    setMapLineIndex(null);
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
      setMapLineIndex(null);
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
      <DailyProgressHeader
        eventDate={draft.event_date}
        maxDate={todayISO()}
        dateDisabled={preview !== null || busy === "load"}
        filters={filters}
        zones={zones}
        segmentOptions={segmentOptions}
        filtersLocked={filtersLocked}
        busy={busy}
        showEmpty={!busy && !rows.length && !error}
        onDateChange={updateDate}
        onFilterChange={updateFilter}
        onOpenPaste={onOpenPaste}
      />

      <DailyProgressBanners
        error={error}
        message={message}
        pendingCode={pendingCode}
        onClearPending={() => setPendingComponentId(null)}
      />

      {!preview ? (
        <>
          {draft.lines.map((line, index) => {
            const eligible = eligibleByLine[index] ?? [];
            return (
              <DailyProgressLineCard
                key={index}
                projectId={projectId}
                batchId={batchId}
                primaryZone={primaryZone}
                index={index}
                line={line}
                rows={rows}
                eligible={eligible}
                definitionOptions={definitionOptions}
                availableWork={availableWork}
                lineCount={draft.lines.length}
                busy={busy}
                expanded={activeLineIndex === index}
                mapOpen={mapLineIndex === index}
                listOpen={listLineIndex === index}
                onToggleExpanded={() =>
                  setActiveLineIndex((current) => current === index ? -1 : index)
                }
                onRemove={() => removeLine(index)}
                onChangeDefinition={(stageDefinitionId) =>
                  changeDefinition(index, stageDefinitionId)
                }
                onUpdateLine={(patch) => updateLine(index, patch)}
                onToggleComponent={(componentId) =>
                  toggleComponent(index, componentId)
                }
                onStageChoice={(componentId, stageId) =>
                  setStageChoice(index, componentId, stageId)
                }
                onSelectAll={() => selectAll(index)}
                onClear={() => clearLine(index)}
                onCopyPrior={() => copyPrior(index)}
                onToggleMap={() =>
                  setMapLineIndex((current) => current === index ? null : index)
                }
                onToggleList={() =>
                  setListLineIndex((current) => current === index ? null : index)
                }
              />
            );
          })}

          <DailyProgressFooter
            busy={busy}
            selectedCount={totalSelected}
            addDisabled={
              busy !== null || draft.lines.length >= MAX_DAILY_PROGRESS_LINES
            }
            onAdd={addLine}
            onPreview={() => void handlePreview()}
          />
        </>
      ) : (
        <DailyProgressPreview
          draft={draft}
          preview={preview}
          definitionOptions={definitionOptions}
          confirmed={confirmed}
          commitReady={commitReady}
          busy={busy}
          totalSelected={totalSelected}
          onConfirmedChange={setConfirmed}
          onEdit={editAgain}
          onSave={() => void handleSave()}
        />
      )}
    </section>
  );
}
