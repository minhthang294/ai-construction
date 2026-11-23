import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  addConstructionBatchComponents,
  correctProgressEvent,
  listComponentProgress,
  listStageDefinitions,
  parseProgressMessage,
  previewConstructionBatchComponents,
} from "../lib/api";
import {
  previewDailyProgress,
  saveDailyProgress,
  type DailyProgressPreviewResponse,
} from "../lib/dailyProgress";
import {
  applyPasteAnswers,
  buildZaloSummary,
  formatPasteDate,
  groupCodesByPrefix,
  pasteIdempotencyKey,
  type PasteAnswers,
  type PasteApplyResult,
  type PasteManualStages,
  type PasteParse,
} from "../lib/progressPaste";
import { deleteDraft, loadDraft, saveDraft } from "../lib/offlineDb";
import { todayISO } from "../lib/componentProgress";
import type { ProgressRow, StageDefinition } from "../lib/componentProgress";
import ConstructionBatchSelector from "./ConstructionBatchSelector";
import DrawingMapPanel from "./DrawingMapPanel";
import {
  useConstructionBatch,
  useConstructionBatches,
} from "../hooks/useConstructionBatch";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";
const PRIMARY =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";
const SECONDARY =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-600 focus-visible:ring-offset-2";

type Props = {
  projectId: string;
  onOpenAcceptance?: () => void;
};

function draftKey(projectId: string) {
  return `paste:${projectId}`;
}

function isNetworkError(cause: unknown) {
  if (cause instanceof ApiError) return false;
  return cause instanceof TypeError ||
    (cause instanceof Error && /fetch|network|offline/i.test(cause.message));
}

function errorMessage(cause: unknown) {
  return cause instanceof Error ? cause.message : "Không xác định được lỗi.";
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

export default function ProgressPastePanel({ projectId, onOpenAcceptance }: Props) {
  const {
    batches,
    loading: batchesLoading,
    error: batchesError,
  } = useConstructionBatches(projectId);
  const { batchId, setBatchId } = useConstructionBatch(
    projectId,
    batches,
    batchesLoading,
  );

  const [text, setText] = useState("");
  const [eventDate, setEventDate] = useState(todayISO());
  const [parsed, setParsed] = useState<PasteParse | null>(null);
  const [answers, setAnswers] = useState<PasteAnswers>({});
  const [manualStages, setManualStages] = useState<PasteManualStages>({});
  const [definitions, setDefinitions] = useState<StageDefinition[]>([]);
  const [applied, setApplied] = useState<PasteApplyResult | null>(null);
  const [preview, setPreview] = useState<DailyProgressPreviewResponse | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"parse" | "preview" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saved, setSaved] = useState<{
    created: number;
    corrections: number;
    batchAdded: number;
  } | null>(null);
  const [zalo, setZalo] = useState("");
  const [pending, setPending] = useState<ProgressRow[] | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    void listStageDefinitions(projectId)
      .then(setDefinitions)
      .catch(() => setDefinitions([]));
  }, [projectId]);

  useEffect(() => {
    let active = true;
    void loadDraft(draftKey(projectId)).then((draft) => {
      if (!active || !draft) return;
      const payload = draft.payload as { text?: string; batchId?: string } | undefined;
      if (payload?.text) {
        setText(payload.text);
        if (draft.date) setEventDate(draft.date);
        if (payload.batchId) setBatchId(payload.batchId);
        setMessage("Đã khôi phục bản nháp tin nhắn trên thiết bị.");
      }
    }).catch(() => undefined);
    return () => { active = false; };
  }, [projectId, setBatchId]);

  const parsedComponentIds = useMemo(
    () =>
      parsed
        ? parsed.lines.flatMap((line) =>
            line.items
              .map((item) => item.component_id)
              .filter((value): value is string => Boolean(value)),
          )
        : [],
    [parsed],
  );

  const answeredAll = parsed
    ? parsed.questions.every((question) => Boolean(answers[question.id]))
    : false;

  function resetFlow() {
    setParsed(null);
    setApplied(null);
    setPreview(null);
    setConfirmed(false);
    setIdempotencyKey(null);
    setSaved(null);
    setZalo("");
    setPending(null);
    setPendingError(null);
    setAnswers({});
    setManualStages({});
    setError(null);
    setMessage(null);
  }

  async function pasteFromClipboard() {
    try {
      const value = await navigator.clipboard.readText();
      if (!value.trim()) {
        setMessage("Clipboard đang trống. Hãy sao chép tin nhắn Zalo rồi thử lại.");
        return;
      }
      setText(value);
      setMessage("Đã dán tin nhắn từ clipboard.");
    } catch {
      setMessage("Trình duyệt không cho đọc clipboard. Hãy chạm vào ô nhập và dán bằng tay.");
    }
  }

  async function keepOfflineDraft() {
    try {
      await saveDraft({
        key: draftKey(projectId),
        projectId,
        date: eventDate,
        payload: { kind: "progress-paste", text, batchId },
        updatedAt: Date.now(),
      });
      setMessage(
        "Không có mạng. Tin nhắn đã được lưu thành bản nháp trên thiết bị; chưa ghi tiến độ và không xếp hàng tự động.",
      );
    } catch {
      setError("Không có mạng và không lưu được bản nháp trên thiết bị.");
    }
  }

  async function parse() {
    if (!text.trim() || busy) return;
    setBusy("parse");
    setError(null);
    setMessage(null);
    try {
      const result = await parseProgressMessage(projectId, {
        text,
        default_date: eventDate || undefined,
        batch_id: batchId || undefined,
      });
      setParsed(result);
      setAnswers({});
      setManualStages({});
      setApplied(null);
      setPreview(null);
      setSaved(null);
      setZalo("");
      setPending(null);
      setEventDate(result.event_date ?? eventDate);
      setMessage("Đã đọc tin nhắn. Trả lời các câu hỏi rồi xem lại trước khi lưu.");
    } catch (cause) {
      if (isNetworkError(cause)) {
        await keepOfflineDraft();
      } else {
        setError(errorMessage(cause));
      }
    } finally {
      setBusy(null);
    }
  }

  function invalidatePreview() {
    setPreview(null);
    setApplied(null);
    setConfirmed(false);
    setIdempotencyKey(null);
  }

  function chooseStage(lineIndex: number, value: string) {
    setManualStages((current) => ({ ...current, [lineIndex]: value }));
    invalidatePreview();
  }

  async function buildPreview() {
    if (!parsed || busy) return;
    const result = applyPasteAnswers(parsed, answers, manualStages, eventDate);
    setApplied(result);
    if (result.errors.length) {
      setError(result.errors.join(" "));
      return;
    }
    if (result.batch_component_ids.length && !batchId) {
      setError("Chọn Đợt thi công trước khi thêm cấu kiện ngoài phạm vi vào đợt.");
      return;
    }
    setBusy("preview");
    setError(null);
    try {
      const data = await previewDailyProgress(projectId, result.payload);
      setApplied({
        ...result,
        savedLines: result.savedLines.map((line, index) => ({
          ...line,
          stage_display_name: data.lines[index]?.stage_display_name ?? null,
        })),
      });
      setPreview(data);
      setIdempotencyKey(pasteIdempotencyKey(text, eventDate));
      setConfirmed(false);
      setMessage(null);
    } catch (cause) {
      if (isNetworkError(cause)) {
        await keepOfflineDraft();
      } else {
        setError(errorMessage(cause));
      }
    } finally {
      setBusy(null);
    }
  }

  async function commit() {
    if (!preview || !applied || !idempotencyKey || !confirmed || busy) return;
    if (!preview.can_commit) return;
    setBusy("save");
    setError(null);
    try {
      const result = await saveDailyProgress(projectId, applied.payload, idempotencyKey);
      let batchAdded = 0;
      let corrections = 0;
      const postErrors: string[] = [];
      if (applied.batch_component_ids.length && batchId) {
        try {
          const codes = applied.savedLines.flatMap((line) => line.codes);
          await previewConstructionBatchComponents(projectId, batchId, codes);
          const added = await addConstructionBatchComponents(
            projectId,
            batchId,
            applied.batch_component_ids,
            `Theo tin nhắn ngày ${formatPasteDate(eventDate)}`,
          );
          batchAdded = added.added;
        } catch (cause) {
          postErrors.push(`Thêm vào đợt: ${errorMessage(cause)}`);
        }
      }
      for (const correction of applied.corrections) {
        try {
          await correctProgressEvent(projectId, correction.event_id, "IN_PROGRESS", correction.reason);
          corrections += 1;
        } catch (cause) {
          postErrors.push(`Sửa sự kiện trước: ${errorMessage(cause)}`);
        }
      }
      setSaved({ created: result.created, corrections, batchAdded });
      await deleteDraft(draftKey(projectId)).catch(() => undefined);
      let rows: ProgressRow[] | null = null;
      try {
        rows = await listComponentProgress(
          projectId,
          { construction_status: "COMPLETED" },
          batchId || undefined,
        );
        setPending(
          rows.filter(
            (row) => row.acceptance_status !== "CONFIRMED" && row.acceptance_status !== "APPROVED",
          ),
        );
        setPendingError(null);
      } catch (cause) {
        setPendingError(errorMessage(cause));
      }
      const savedCount = applied.savedLines.reduce(
        (sum, line) => sum + line.codes.length,
        0,
      );
      const pendingCount = rows
        ? rows.filter(
            (row) => row.acceptance_status !== "CONFIRMED" && row.acceptance_status !== "APPROVED",
          ).length
        : savedCount;
      setZalo(
        buildZaloSummary({
          eventDate,
          lines: applied.savedLines,
          pendingAcceptance: pendingCount,
        }),
      );
      setCopied(false);
      setPreview(null);
      setConfirmed(false);
      setApplied(null);
      setParsed(null);
      if (postErrors.length) {
        setError(postErrors.join(" "));
      } else {
        setMessage(`Đã ghi ${result.created} sự kiện tiến độ.`);
      }
    } catch (cause) {
      // Same preview + key stay valid for an identical retry.
      if (isNetworkError(cause)) {
        await keepOfflineDraft();
      } else {
        setError(errorMessage(cause));
      }
    } finally {
      setBusy(null);
    }
  }

  const stageChoicesFor = (lineType: string) =>
    definitions.filter((definition) => definition.type === lineType);

  const stageOptionsForLine = (line: PasteParse["lines"][number]) => {
    const options = [
      ...(line.stage_candidates ?? []).map((candidate) => ({
        id: candidate.stage_definition_id,
        name: candidate.name,
      })),
      ...stageChoicesFor(line.component_type).map((definition) => ({
        id: definition.id,
        name: definition.name,
      })),
    ];
    return options.filter(
      (candidate, index) =>
        options.findIndex((item) => item.id === candidate.id) === index,
    );
  };

  return (
    <section className="mx-auto w-full max-w-4xl space-y-4">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#405e9b]">
          Hiện trường
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
          Ghi tiến độ từ tin nhắn
        </h1>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          Dán tin nhắn Zalo, trả lời câu hỏi, xem lại rồi mới ghi. Không tự ghi khi chưa xác nhận.
        </p>
      </header>

      <ConstructionBatchSelector
        batches={batches}
        value={batchId}
        onChange={(value) => {
          setBatchId(value);
          resetFlow();
        }}
        loading={batchesLoading}
        error={batchesError}
      />

      {error ? (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}

      <section className="app-card app-card-pad space-y-3">
        <label className="block text-xs font-medium text-slate-700">
          Tin nhắn hiện trường
          <textarea
            className={`${FIELD} min-h-40`}
            value={text}
            maxLength={12000}
            placeholder={"Ví dụ:\nCọc đục ngày 22/11\nI49, 51,55,57\nH65,62\nG50,65\nF54,55"}
            onChange={(event) => {
              if (parsed) resetFlow();
              setText(event.target.value);
              setMessage(null);
            }}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={SECONDARY} onClick={() => void pasteFromClipboard()}>
            Dán từ clipboard
          </button>
          <label className="flex min-h-11 items-center gap-2 text-xs font-medium text-slate-700">
            Ngày mặc định
            <input
              type="date"
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-2 text-sm"
              value={eventDate}
              max={todayISO()}
              onChange={(event) => setEventDate(event.target.value)}
            />
          </label>
          <button
            type="button"
            className={`${PRIMARY} flex-1 sm:flex-none`}
            disabled={busy !== null || !text.trim()}
            onClick={() => void parse()}
          >
            {busy === "parse" ? "Đang đọc tin nhắn…" : "Đọc tin nhắn"}
          </button>
        </div>
      </section>

      {parsed ? (
        <>
          <section className="app-card app-card-pad space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Kết quả đọc</h2>
                <p className="text-xs text-slate-600">
                  {parsed.date_source === "text" ? "Ngày lấy từ tin nhắn" : "Ngày mặc định"} · kiểm tra lại trước khi ghi
                </p>
              </div>
              <label className="text-xs font-medium text-slate-700">
                Ngày thi công
                <input
                  type="date"
                  className={`${FIELD} w-auto`}
                  value={eventDate}
                  max={todayISO()}
                  onChange={(event) => {
                    setEventDate(event.target.value);
                    invalidatePreview();
                  }}
                />
              </label>
            </div>

            {parsed.warnings?.length ? (
              <ul role="alert" className="list-disc space-y-1 rounded-lg bg-amber-50 p-3 pl-7 text-xs text-amber-900">
                {parsed.warnings.map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
                ))}
              </ul>
            ) : null}

            <div className="space-y-3">
              {parsed.lines.map((line, lineIndex) => (
                <article key={`${line.work_text}-${lineIndex}`} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">
                        {line.component_type === "pile" ? "Cọc" : "Dầm"} · {line.work_text}
                      </h3>
                      <p className="text-xs text-slate-600">{line.items.length} mã trong dòng</p>
                    </div>
                    <label className="min-w-0 text-xs font-medium text-slate-700">
                      Công đoạn
                      <select
                        className={`${FIELD} max-w-56`}
                        value={
                          manualStages[lineIndex] ??
                          (line.stage_candidates?.length === 1
                            ? line.stage_candidates[0].stage_definition_id
                            : "")
                        }
                        onChange={(event) => chooseStage(lineIndex, event.target.value)}
                      >
                        <option value="">— Chọn công đoạn —</option>
                        {stageOptionsForLine(line).map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>
                            {candidate.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="mt-2 space-y-1">
                    {groupCodesByPrefix(
                      line.items.map((item) => ({
                        code: item.code,
                        unknown: !item.component_id,
                      })),
                    ).map(([prefix, items]) => (
                      <div key={prefix} className="flex flex-wrap items-center gap-1">
                        <span className="text-[11px] font-semibold uppercase text-slate-500">{prefix}</span>
                        {items.map((item, index) => (
                          <span
                            key={`${item.code}-${index}`}
                            className={`rounded-full border px-2 py-0.5 font-mono text-xs ${
                              item.unknown
                                ? "border-red-300 bg-red-50 text-red-800"
                                : "border-slate-200 bg-slate-50 text-slate-700"
                            }`}
                          >
                            {item.code}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            {parsedComponentIds.length ? (
              <details className="rounded-xl border border-slate-200">
                <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between px-3 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden">
                  Xem trên mặt bằng
                  <span className="text-xs font-normal text-slate-500">{parsedComponentIds.length} cấu kiện</span>
                </summary>
                <div className="border-t border-slate-100 p-2">
                  <DrawingMapPanel
                    projectId={projectId}
                    batchId={batchId}
                    selection={{
                      selectedIds: parsedComponentIds,
                      selectableIds: parsedComponentIds,
                      disabled: true,
                      onToggle: () => undefined,
                    }}
                  />
                </div>
              </details>
            ) : (
              <p className="rounded-lg border border-dashed border-slate-300 p-3 text-sm text-slate-600">
                Chưa có mã cấu kiện hợp lệ để hiện trên mặt bằng.
              </p>
            )}
          </section>

          {parsed.questions.length ? (
            <section className="app-card app-card-pad space-y-3" aria-labelledby="paste-questions">
              <div>
                <h2 id="paste-questions" className="text-base font-semibold text-slate-900">
                  Câu hỏi cần xác nhận ({parsed.questions.length})
                </h2>
                <p className="text-xs text-slate-600">Phải trả lời tất cả trước khi xem lại và ghi.</p>
              </div>
              {parsed.questions.map((question) => (
                <fieldset key={question.id} className="rounded-xl border border-slate-200 p-3">
                  <legend className="px-1 text-sm font-medium text-slate-800">{question.message_vi}</legend>
                  {question.codes?.length ? (
                    <p className="mt-1 break-words font-mono text-xs text-slate-600">
                      {question.codes.join(", ")}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {question.options.map((option) => {
                      const active = answers[question.id] === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          aria-pressed={active}
                          className={`min-h-11 rounded-lg border px-3 text-sm font-semibold ${FOCUS} ${
                            active
                              ? "border-slate-800 bg-slate-800 text-white"
                              : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
                          }`}
                          onClick={() => {
                            setAnswers((current) => ({ ...current, [question.id]: option.value }));
                            invalidatePreview();
                          }}
                        >
                          {option.label_vi}
                        </button>
                      );
                    })}
                  </div>
                </fieldset>
              ))}
            </section>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={`${PRIMARY} flex-1`}
              disabled={busy !== null || !answeredAll}
              onClick={() => void buildPreview()}
            >
              {busy === "preview" ? "Đang kiểm tra…" : "Xem lại trước khi ghi"}
            </button>
          </div>
        </>
      ) : null}

      {preview ? (
        <section className="app-card app-card-pad space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">Xem lại trước khi lưu</h2>
            <span className="text-xs text-slate-600">
              {formatPasteDate(eventDate)} · {preview.lines.length} dòng
            </span>
          </div>
          {preview.warnings.length ? (
            <ul role="alert" className="list-disc space-y-1 rounded-lg bg-amber-50 p-3 pl-7 text-xs text-amber-900">
              {preview.warnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          ) : null}
          <div className="space-y-2">
            {preview.lines.map((line) => (
              <div key={line.line_index} className="rounded-lg border border-slate-200 p-2 text-sm">
                <div className="flex flex-wrap justify-between gap-1">
                  <span className="font-medium text-slate-900">Dòng {line.line_index + 1}</span>
                  <span className="text-xs text-slate-600">
                    {line.ready_count}/{line.count} sẵn sàng
                  </span>
                </div>
                {line.stage_display_name ? (
                  <p className="mt-1 break-words text-xs font-medium text-slate-800">
                    {line.stage_display_name}
                  </p>
                ) : null}
                <p className="mt-1 break-words font-mono text-xs text-slate-700">
                  {line.components.map((component) => component.canonical_code).join(", ")}
                </p>
              </div>
            ))}
          </div>
          <label className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm text-slate-800">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
              checked={confirmed}
              disabled={!preview.can_commit || busy !== null}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              Tôi đã kiểm tra đúng {applied?.savedLines.reduce((sum, line) => sum + line.component_ids.length, 0) ?? 0} cấu kiện
              và xác nhận ghi ngày {formatPasteDate(eventDate)}.
            </span>
          </label>
          {!preview.can_commit ? (
            <p className="text-sm text-red-800">
              Máy chủ chưa cho ghi. Quay lại chỉnh câu trả lời/công đoạn rồi kiểm tra lại.
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={SECONDARY}
              disabled={busy !== null}
              onClick={() => {
                setPreview(null);
                setConfirmed(false);
              }}
            >
              Quay lại sửa
            </button>
            <button
              type="button"
              className={`${PRIMARY} flex-1`}
              disabled={!confirmed || !preview.can_commit || busy !== null}
              onClick={() => void commit()}
            >
              {busy === "save" ? "Đang ghi tiến độ…" : "Ghi tiến độ"}
            </button>
          </div>
        </section>
      ) : null}

      {saved ? (
        <section className="app-card app-card-pad space-y-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Đã ghi tiến độ</h2>
            <p className="mt-1 text-sm text-slate-700">
              {saved.created} sự kiện · {saved.corrections} sửa sự kiện trước
              {saved.batchAdded ? ` · ${saved.batchAdded} thêm vào đợt` : ""}.
            </p>
          </div>
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-slate-900">Tin nhắn Zalo</h3>
              <button
                type="button"
                className={SECONDARY}
                onClick={async () => {
                  setCopied(await copyText(zalo));
                }}
              >
                {copied ? "Đã sao chép" : "Sao chép"}
              </button>
            </div>
            <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-sm text-slate-800">
              {zalo}
            </pre>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Đã thi công xong, chưa nghiệm thu
              {pending ? ` (${pending.length})` : ""}
            </h3>
            {pendingError ? <p role="alert" className="mt-1 text-sm text-red-700">{pendingError}</p> : null}
            {pending === null ? (
              <p role="status" className="mt-1 text-sm text-slate-600">Đang tải danh sách…</p>
            ) : pending.length ? (
              <ul className="mt-2 max-h-56 space-y-1 overflow-auto">
                {pending.map((row) => (
                  <li key={row.id} className="flex flex-wrap items-center justify-between gap-1 rounded border border-slate-200 p-2 text-xs">
                    <span className="font-mono font-semibold">{row.canonical_code}</span>
                    <span className="text-slate-600">{row.zone} · PĐ{row.segment_number}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-slate-600">Không còn cấu kiện chờ nghiệm thu trong đợt.</p>
            )}
            {onOpenAcceptance ? (
              <button type="button" className={`${SECONDARY} mt-2`} onClick={onOpenAcceptance}>
                Mở Nghiệm thu
              </button>
            ) : null}
          </div>
          <button
            type="button"
            className={SECONDARY}
            onClick={() => {
              resetFlow();
              setText("");
            }}
          >
            Dán tin nhắn khác
          </button>
        </section>
      ) : null}
    </section>
  );
}
