import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createJournalExport,
  createJournalSnapshot,
  downloadJournalExport,
  downloadJournalSnapshot,
  getJournalPreview,
  listJournalExports,
  listJournalSnapshots,
} from "../lib/api";
import {
  canCreateJournalSnapshot,
  journalBlockerLabel,
  type JournalExport,
  type JournalExportFormat,
  type JournalPreview,
  type JournalSnapshot,
} from "../lib/journal";
import { todayISO } from "../lib/componentProgress";
import { formatISODate } from "../lib/datetime";

type Props = { projectId: string; initialDate?: string | null };

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

function shortHash(value: string): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

export default function JournalPanel({ projectId, initialDate }: Props) {
  const [date, setDate] = useState(initialDate || todayISO());
  const [preview, setPreview] = useState<JournalPreview | null>(null);
  const [snapshots, setSnapshots] = useState<JournalSnapshot[]>([]);
  const [exports, setExports] = useState<JournalExport[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<
    "history" | "preview" | "snapshot" | "export" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setBusy("history");
    try {
      const [snapshotRows, exportRows] = await Promise.all([
        listJournalSnapshots(projectId, date),
        listJournalExports(projectId, date),
      ]);
      setSnapshots(snapshotRows);
      setExports(exportRows);
      setError(null);
    } catch (err) {
      setSnapshots([]);
      setExports([]);
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [projectId, date]);

  useEffect(() => {
    setPreview(null);
    setConfirmed(false);
    setMessage(null);
    void loadHistory();
  }, [loadHistory]);

  async function handlePreview() {
    setBusy("preview");
    setError(null);
    setMessage(null);
    setConfirmed(false);
    try {
      setPreview(await getJournalPreview(projectId, date));
    } catch (err) {
      setPreview(null);
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSnapshot() {
    if (!preview || !canCreateJournalSnapshot(preview, confirmed) || busy) return;
    setBusy("snapshot");
    setError(null);
    try {
      const created = await createJournalSnapshot(
        projectId,
        date,
        preview.preview_sha256,
      );
      setMessage(
        `Đã tạo snapshot đã duyệt cho ngày ${formatISODate(date)} (${shortHash(created.sha256)}).`,
      );
      await loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleExport(
    snapshot: JournalSnapshot,
    format: JournalExportFormat,
  ) {
    setBusy("export");
    setError(null);
    setMessage(null);
    try {
      const result = await createJournalExport(
        projectId,
        date,
        snapshot.id,
        format,
      );
      await downloadJournalExport(result);
      setMessage(
        `Đã xuất nhật ký ${format.toUpperCase()} từ snapshot ${shortHash(snapshot.sha256)}.`,
      );
      await loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleDownloadSnapshot(snapshot: JournalSnapshot) {
    try {
      await downloadJournalSnapshot(snapshot);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
        Nhật ký chỉ lấy dữ liệu thực tế đã ghi. Mục nghiệm thu chỉ hiện BBNT{" "}
        <strong>đã xác nhận</strong>; ngày không có BBNT sẽ để trống và ghi rõ.
        Xuất file chỉ dùng snapshot đã duyệt.
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-medium text-gray-600">
            Ngày nhật ký
            <input
              type="date"
              className="mt-1 block min-h-11 rounded-lg border border-gray-300 px-3 text-sm"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-medium text-white disabled:bg-gray-300"
            disabled={busy !== null || !date}
            onClick={() => void handlePreview()}
          >
            {busy === "preview" ? "Đang xem trước…" : "Xem trước nhật ký"}
          </button>
          <button
            type="button"
            className="min-h-11 rounded-lg border border-gray-300 px-3 text-sm font-medium text-gray-700 disabled:bg-gray-100"
            disabled={busy === "history"}
            onClick={() => void loadHistory()}
          >
            Tải lại lịch sử
          </button>
        </div>
        {error ? (
          <p
            role="alert"
            className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-800"
          >
            {error}
          </p>
        ) : null}
        {message ? (
          <p
            role="status"
            className="mt-3 rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-800"
          >
            {message}
          </p>
        ) : null}
      </div>

      {preview ? (
        <div className="space-y-3 rounded-xl border border-gray-300 bg-white p-3 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h4 className="text-base font-semibold">
                {preview.project_title} · {preview.date_display}
              </h4>
              <p className="text-xs text-gray-500">
                Preview {shortHash(preview.preview_sha256)} ·{" "}
                {preview.evidence_summary.evidence_count} ảnh chứng cứ ·{" "}
                {preview.acceptance_count} BBNT xác nhận
              </p>
            </div>
            <span
              className={`rounded-full px-2 py-1 text-xs font-medium ${
                preview.snapshot_eligible
                  ? "bg-emerald-100 text-emerald-900"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {preview.snapshot_eligible
                ? "Sẵn sàng tạo snapshot"
                : "Chưa thể tạo snapshot"}
            </span>
          </div>

          {preview.blockers.length ? (
            <ul className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-900">
              {preview.blockers.map((blocker) => (
                <li key={blocker}>- {journalBlockerLabel(blocker)}</li>
              ))}
            </ul>
          ) : null}
          {preview.warnings.length ? (
            <ul className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950">
              {preview.warnings.map((warning) => (
                <li key={warning}>- {warning}</li>
              ))}
            </ul>
          ) : null}
          {preview.evidence_summary.omitted_evidence_count ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950">
              {preview.evidence_summary.omitted_evidence_count} tham chiếu chứng
              cứ chưa xác nhận hoặc không phân giải được sẽ bị bỏ khỏi snapshot.
            </p>
          ) : null}

          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-800">
            {preview.preview_text}
          </pre>

          <label className="flex items-start gap-2 text-sm text-gray-800">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4"
              checked={confirmed}
              disabled={!preview.snapshot_eligible || busy !== null}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              Tôi đã kiểm tra đúng nội dung preview trên, gồm{" "}
              {preview.evidence_summary.evidence_count} ảnh chứng cứ đã xác nhận
              và {preview.acceptance_count} BBNT đã xác nhận.
            </span>
          </label>
          <button
            type="button"
            className="min-h-11 w-full rounded-lg bg-green-700 px-4 text-sm font-medium text-white active:bg-green-800 disabled:bg-gray-300"
            disabled={
              !canCreateJournalSnapshot(preview, confirmed) || busy !== null
            }
            onClick={() => void handleSnapshot()}
          >
            {busy === "snapshot"
              ? "Đang tạo snapshot…"
              : "Tạo snapshot nhật ký đã duyệt"}
          </button>
        </div>
      ) : null}

      <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
        <h4 className="text-base font-semibold">
          Snapshot đã duyệt · {formatISODate(date)}
        </h4>
        <p className="mt-1 text-xs text-gray-500">
          Chỉ snapshot đã duyệt mới xuất được file. PDF/DOCX có danh mục chứng
          cứ; ZIP kèm bytes ảnh đã xác nhận.
        </p>
        <div className="mt-2 space-y-2">
          {snapshots.map((snapshot) => (
            <div
              key={snapshot.id}
              className="rounded-lg border border-gray-200 p-2 text-xs"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-mono">{shortHash(snapshot.sha256)}</span>
                <span className="text-gray-500">
                  {new Date(snapshot.reviewed_at).toLocaleString("vi-VN")}
                </span>
              </div>
              <p className="mt-1 text-gray-600">
                {snapshot.evidence_count} ảnh · {snapshot.acceptance_count} BBNT
                {snapshot.omitted_evidence_count
                  ? ` · bỏ ${snapshot.omitted_evidence_count} tham chiếu`
                  : ""}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="min-h-9 rounded-lg border border-gray-300 px-2 font-medium text-gray-700"
                  onClick={() => void handleDownloadSnapshot(snapshot)}
                >
                  Tải JSON
                </button>
                {(["pdf", "docx", "zip"] as JournalExportFormat[]).map(
                  (format) => (
                    <button
                      key={format}
                      type="button"
                      className="min-h-9 rounded-lg bg-slate-800 px-2 font-medium text-white disabled:bg-gray-300"
                      disabled={busy !== null}
                      onClick={() => void handleExport(snapshot, format)}
                    >
                      {format.toUpperCase()}
                    </button>
                  ),
                )}
              </div>
            </div>
          ))}
          {snapshots.length === 0 ? (
            <p className="rounded-lg border border-gray-200 p-3 text-sm text-gray-500">
              Chưa có snapshot đã duyệt cho ngày này.
            </p>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
        <h4 className="text-base font-semibold">Lịch sử xuất nhật ký</h4>
        <div className="mt-2 space-y-1 text-xs">
          {exports.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 p-2"
            >
              <span className="font-medium uppercase">{item.format}</span>
              <span className="font-mono text-gray-500">
                {shortHash(item.sha256)}
              </span>
              <span className="text-gray-500">
                {new Date(item.generated_at).toLocaleString("vi-VN")}
              </span>
              <button
                type="button"
                className="min-h-8 rounded-lg border border-gray-300 px-2 font-medium text-gray-700"
                onClick={() =>
                  void downloadJournalExport(item).catch((err) =>
                    setError(errorMessage(err)),
                  )
                }
              >
                Tải
              </button>
            </div>
          ))}
          {exports.length === 0 ? (
            <p className="rounded-lg border border-gray-200 p-3 text-sm text-gray-500">
              Chưa có file nhật ký được xuất.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
