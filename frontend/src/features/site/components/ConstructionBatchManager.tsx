import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  addConstructionBatchComponents,
  createConstructionBatch,
  getConstructionBatch,
  previewConstructionBatchComponents,
  removeConstructionBatchComponent,
} from "../lib/api";
import type {
  BatchPreview,
  ConstructionBatch,
  ConstructionBatchDetail,
} from "../lib/batches";
import { parseQuickCodes } from "../lib/quickCodeEntry";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";
const PRIMARY =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";
const SECONDARY =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Không xác định được lỗi.";
}

export default function ConstructionBatchManager({
  projectId,
  batchId,
  batches,
  onSelect,
  onChanged,
}: {
  projectId: string;
  batchId: string;
  batches: ConstructionBatch[];
  onSelect: (batchId: string) => void;
  onChanged: () => void;
}) {
  const selected = batches.find((batch) => batch.id === batchId) ?? null;
  const [detail, setDetail] = useState<ConstructionBatchDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [text, setText] = useState("");
  const [reason, setReason] = useState("Thi công cùng đợt");
  const [preview, setPreview] = useState<BatchPreview | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"create" | "preview" | "add" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!batchId) {
      setDetail(null);
      return;
    }
    try {
      setDetail(await getConstructionBatch(projectId, batchId));
      setDetailError(null);
    } catch (cause) {
      setDetail(null);
      setDetailError(messageOf(cause));
    }
  }, [batchId, projectId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const parsedCodes = useMemo(() => parseQuickCodes(text).codes, [text]);
  const ambiguousResolved = preview
    ? preview.ambiguous.every((item) => choices[item.code])
    : false;
  const canAdd = Boolean(
    preview &&
      preview.matched.length + Object.values(choices).filter(Boolean).length > 0 &&
      preview.missing.length === 0 &&
      ambiguousResolved &&
      busy === null,
  );

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy("create");
    setError(null);
    try {
      const created = await createConstructionBatch(projectId, {
        name: name.trim(),
        note: note.trim() || null,
      });
      setName("");
      setNote("");
      setMessage(`Đã tạo đợt “${created.name}”.`);
      onChanged();
      onSelect(created.id);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  async function previewCodes() {
    if (!batchId || !parsedCodes.length || busy) return;
    setBusy("preview");
    setError(null);
    setMessage(null);
    setChoices({});
    try {
      setPreview(await previewConstructionBatchComponents(projectId, batchId, parsedCodes));
    } catch (cause) {
      setPreview(null);
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  async function add() {
    if (!batchId || !preview || !canAdd) return;
    const ids = [
      ...preview.matched.map((item) => item.component.id),
      ...Object.values(choices).filter(Boolean),
    ];
    setBusy("add");
    setError(null);
    try {
      const result = await addConstructionBatchComponents(
        projectId,
        batchId,
        Array.from(new Set(ids)),
        reason.trim() || undefined,
      );
      setMessage(`Đã thêm ${result.added} cấu kiện vào đợt.`);
      setText("");
      setPreview(null);
      setChoices({});
      await loadDetail();
      onChanged();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  async function remove(componentId: string, code: string) {
    if (!batchId || busy) return;
    if (!window.confirm(`Bỏ ${code} khỏi đợt thi công?`)) return;
    setBusy("remove");
    setError(null);
    try {
      await removeConstructionBatchComponent(
        projectId,
        batchId,
        componentId,
        "Bỏ khỏi đợt từ màn hình quản lý",
      );
      setMessage(`Đã bỏ ${code} khỏi đợt.`);
      await loadDetail();
      onChanged();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-sm font-semibold text-slate-900 [&::-webkit-details-marker]:hidden">
        Quản lý đợt thi công
        <span className="text-xs font-normal text-slate-500">
          {selected ? `${selected.name} · ${selected.component_count} cấu kiện` : "Tạo và gom mã cấu kiện"}
        </span>
      </summary>
      <div className="space-y-4 border-t border-slate-100 p-3">
        <form onSubmit={create} className="space-y-2">
          <p className="text-sm font-semibold text-slate-900">Tạo đợt mới</p>
          <label className="block text-xs font-medium text-slate-700">
            Tên đợt
            <input
              className={FIELD}
              value={name}
              maxLength={255}
              placeholder="Ví dụ: PD2 Cầu chính · đợt 1"
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label className="block text-xs font-medium text-slate-700">
            Ghi chú
            <input
              className={FIELD}
              value={note}
              maxLength={2000}
              placeholder="Tùy chọn"
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <button type="submit" className={PRIMARY} disabled={busy !== null || !name.trim()}>
            {busy === "create" ? "Đang tạo…" : "Tạo đợt"}
          </button>
        </form>

        {error ? <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-800">{error}</p> : null}
        {message ? <p role="status" className="rounded-lg bg-emerald-50 p-2 text-sm text-emerald-800">{message}</p> : null}

        {selected ? (
          <div className="space-y-3 border-t border-slate-200 pt-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">
                Thêm cấu kiện vào “{selected.name}”
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Mã được tìm trên toàn công trình. Mã trùng ở nhiều khu/phân đoạn phải chọn tay.
              </p>
            </div>
            <label className="block text-xs font-medium text-slate-700">
              Mã cấu kiện
              <input
                className={FIELD}
                value={text}
                placeholder="Ví dụ: A-B-153, B-D-153 hoặc F67,64"
                onChange={(event) => {
                  setText(event.target.value);
                  setPreview(null);
                  setChoices({});
                }}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={SECONDARY}
                disabled={busy !== null || !parsedCodes.length}
                onClick={() => void previewCodes()}
              >
                {busy === "preview" ? "Đang kiểm tra…" : "Xem trước mã"}
              </button>
            </div>

            {preview ? (
              <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs">
                <p className="font-medium text-slate-800">
                  Khớp {preview.matched.length} · mơ hồ {preview.ambiguous.length} · thiếu {preview.missing.length}
                </p>
                {preview.matched.map((item) => (
                  <p key={item.component.id} className="break-words text-slate-700">
                    <span className="font-mono font-semibold">{item.component.canonical_code}</span>{" "}
                    · {item.component.zone} PĐ{item.component.segment_number}
                  </p>
                ))}
                {preview.ambiguous.map((item) => (
                  <fieldset key={item.code} className="rounded-lg border border-amber-200 bg-amber-50 p-2">
                    <legend className="px-1 font-semibold text-amber-900">
                      Mã {item.code} có {item.candidates.length} cấu kiện
                    </legend>
                    <div className="space-y-1">
                      {item.candidates.map((candidate) => (
                        <label key={candidate.id} className="flex min-h-11 items-center gap-2 text-slate-800">
                          <input
                            type="radio"
                            name={`batch-code-${item.code}`}
                            checked={choices[item.code] === candidate.id}
                            onChange={() =>
                              setChoices((current) => ({ ...current, [item.code]: candidate.id }))
                            }
                          />
                          <span className="break-words">
                            {candidate.canonical_code} · {candidate.zone} PĐ{candidate.segment_number}
                          </span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
                {preview.missing.length ? (
                  <p className="break-words font-medium text-red-700">
                    Không tìm thấy: {preview.missing.join(", ")}
                  </p>
                ) : null}
                {preview.already_in_batch.length ? (
                  <p className="break-words text-slate-600">
                    Đã có trong đợt: {preview.already_in_batch.join(", ")}
                  </p>
                ) : null}
                <label className="block font-medium text-slate-700">
                  Lý do (tùy chọn)
                  <input
                    className={FIELD}
                    value={reason}
                    maxLength={1000}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
                <button type="button" className={PRIMARY} disabled={!canAdd} onClick={() => void add()}>
                  {busy === "add" ? "Đang thêm…" : "Xác nhận thêm cấu kiện"}
                </button>
              </div>
            ) : null}

            <div className="space-y-2 border-t border-slate-200 pt-3">
              <p className="text-sm font-semibold text-slate-900">
                Cấu kiện trong đợt ({detail?.components.length ?? selected.component_count})
              </p>
              {detailError ? <p role="alert" className="text-sm text-red-700">{detailError}</p> : null}
              {detail?.components.length ? (
                <ul className="space-y-1">
                  {detail.components.map((component) => (
                    <li
                      key={component.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm"
                    >
                      <span className="min-w-0 break-words">
                        <span className="font-mono font-semibold">{component.canonical_code}</span>
                        {" · "}
                        {component.zone} PĐ{component.segment_number}
                      </span>
                      <button
                        type="button"
                        className={SECONDARY}
                        disabled={busy !== null}
                        onClick={() => void remove(component.id, component.canonical_code)}
                      >
                        Bỏ
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">Chưa có cấu kiện trong đợt này.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="border-t border-slate-200 pt-3 text-sm text-slate-600">
            Chọn một đợt trong ô “Đợt thi công” để thêm hoặc bỏ cấu kiện.
          </p>
        )}
      </div>
    </details>
  );
}
