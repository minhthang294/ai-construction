import ParticipantsEditor from "../components/ParticipantsEditor";
import TriStateChecklist from "../components/TriStateChecklist";
import { shouldOfferRevision } from "../lib/formGuard";
import {
  dailyReportHref,
  draftStatusSummary,
  draftTitle,
} from "./acceptancePageModel";
import type { RecordDraft } from "./acceptancePageModel";
import type { LinkedDailyReport, YesNo } from "../types";

type Props = {
  projectId: string;
  draft: RecordDraft;
  message: string | null;
  error: string | null;
  busy: boolean;
  reportLinks: Record<string, LinkedDailyReport | null>;
  onUpdate: (updater: (current: RecordDraft) => RecordDraft) => void;
  onSave: () => void;
  onClose: () => void;
  onConfirm: () => void;
  onPreview: () => void;
  onRevision: () => void;
  onExport: (kind: "pyc" | "bbnt", format: "xlsx" | "pdf") => void;
};

export default function RecordDraftEditor({
  projectId,
  draft,
  message,
  error,
  busy,
  reportLinks,
  onUpdate,
  onSave,
  onClose,
  onConfirm,
  onPreview,
  onRevision,
  onExport,
}: Props) {
  const report = reportLinks[draft.request_id];
  return (
    <div className="space-y-4 rounded-xl bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{draftTitle(draft)}</h2>
        <span className="text-sm rounded bg-slate-100 px-2 py-1 text-slate-700">
          {draftStatusSummary(draft)}
        </span>
      </div>

      {draft.stale && (
        <div className="rounded bg-amber-50 p-2 text-sm text-amber-900">
          {draft.stale_warning ||
            "PYC đã thay đổi sau khi BBNT được tạo; BBNT không tự sửa."}
        </div>
      )}

      <dl className="grid gap-2 rounded bg-slate-50 p-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">Tên công trình</dt>
          <dd className="font-medium">{draft.project_name || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Chủ đầu tư</dt>
          <dd className="font-medium">{draft.client || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Địa điểm công trình</dt>
          <dd className="font-medium">{draft.project_location || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Vị trí nghiệm thu</dt>
          <dd className="font-medium">{draft.location || "—"}</dd>
        </div>
      </dl>
      <p className="text-sm text-slate-500">
        Thông tin công trình được lấy lại từ PYC/Thiết lập công trình; không cần nhập lại.
      </p>

      {report && (
        <div className="rounded bg-teal-50 p-2 text-sm text-teal-900">
          Báo cáo ngày liên kết: {report.report_date} ({report.status}) —{" "}
          <a
            className="inline-flex min-h-11 items-center underline"
            href={dailyReportHref(projectId, report.report_date)}
            target="_blank"
            rel="noreferrer"
          >
            xem dữ liệu
          </a>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Ngày nghiệm thu
          <input
            type="date"
            className="mt-1 w-full rounded border p-3"
            value={draft.record_date}
            disabled={draft.status === "confirmed"}
            onChange={(event) => onUpdate((current) => ({ ...current, record_date: event.target.value }))}
          />
        </label>
        <label className="block text-sm">
          Bắt đầu
          <input
            className="mt-1 w-full rounded border p-3"
            value={draft.start_time}
            placeholder="Ví dụ: 15h00"
            disabled={draft.status === "confirmed"}
            onChange={(event) => onUpdate((current) => ({ ...current, start_time: event.target.value }))}
          />
        </label>
        <label className="block text-sm">
          Kết thúc
          <input
            className="mt-1 w-full rounded border p-3"
            value={draft.end_time}
            placeholder="Ví dụ: 16h20"
            disabled={draft.status === "confirmed"}
            onChange={(event) => onUpdate((current) => ({ ...current, end_time: event.target.value }))}
          />
        </label>
        <label className="block text-sm">
          So với thiết kế
          <select
            className="mt-1 w-full rounded border p-3"
            value={draft.design_compliance}
            disabled={draft.status === "confirmed"}
            onChange={(event) =>
              onUpdate((current) => ({
                ...current,
                design_compliance: event.target.value as YesNo | "",
              }))
            }
          >
            <option value="">Chưa đánh giá</option>
            <option value="yes">Đảm bảo</option>
            <option value="no">Không đảm bảo</option>
          </select>
        </label>
        <label className="block text-sm">
          So với chỉ dẫn kỹ thuật
          <select
            className="mt-1 w-full rounded border p-3"
            value={draft.technical_compliance}
            disabled={draft.status === "confirmed"}
            onChange={(event) =>
              onUpdate((current) => ({
                ...current,
                technical_compliance: event.target.value as YesNo | "",
              }))
            }
          >
            <option value="">Chưa đánh giá</option>
            <option value="yes">Đạt yêu cầu</option>
            <option value="no">Không đạt yêu cầu</option>
          </select>
        </label>
      </div>

      <label className="block text-sm">
        Ý kiến khác
        <textarea
          className="mt-1 w-full rounded border p-3"
          rows={2}
          value={draft.other_notes}
          disabled={draft.status === "confirmed"}
          onChange={(event) => onUpdate((current) => ({ ...current, other_notes: event.target.value }))}
        />
      </label>

      <ParticipantsEditor
        items={draft.participants}
        disabled={draft.status === "confirmed"}
        onChange={(participants) => onUpdate((current) => ({ ...current, participants }))}
      />

      <TriStateChecklist
        items={draft.checklist}
        disabled={draft.status === "confirmed"}
        onChange={(checklist) => onUpdate((current) => ({ ...current, checklist }))}
      />

      <label className="block text-sm">
        Ghi chú kết luận (chỉ người xác nhận ghi)
        <textarea
          className="mt-1 w-full rounded border p-3"
          rows={2}
          value={draft.conclusion_note}
          disabled={draft.status === "confirmed"}
          onChange={(event) => onUpdate((current) => ({ ...current, conclusion_note: event.target.value }))}
        />
      </label>

      <div className="sticky bottom-[4.75rem] z-20 -mx-4 space-y-2 border-t border-slate-200 bg-white/95 p-3 backdrop-blur supports-[backdrop-filter]:bg-white/85 lg:bottom-0 lg:-mx-4">
        {message && (
          <p role="status" className="rounded bg-emerald-50 p-2 text-sm text-emerald-900">
            {message}
          </p>
        )}
        {error && (
          <p role="alert" className="rounded bg-rose-50 p-2 text-sm text-rose-900">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {draft.status !== "confirmed" && (
            <button
              type="button"
              onClick={onSave}
              disabled={busy}
              className="min-h-11 rounded bg-teal-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Đang lưu..." : "Lưu BBNT nháp"}
            </button>
          )}
          {draft.status !== "confirmed" && draft.id && (
            <button
              type="button"
              onClick={onConfirm}
              disabled={busy}
              className="min-h-11 rounded bg-emerald-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
            >
              Xác nhận BBNT
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded border px-4 py-3"
          >
            Đóng
          </button>
          <details className="w-full rounded border border-slate-200">
            <summary className="flex min-h-11 cursor-pointer items-center px-3 text-sm font-medium text-slate-700">
              Xuất hồ sơ &amp; xem trước
            </summary>
            <div className="flex flex-wrap gap-2 border-t border-slate-200 p-2">
              {draft.id && (
                <button
                  type="button"
                  onClick={onPreview}
                  disabled={busy}
                  className="min-h-11 rounded border px-4 py-3 text-sm disabled:opacity-50"
                >
                  Xem trước
                </button>
              )}
              {draft.id && shouldOfferRevision(draft.status, draft.stale) && (
                <button
                  type="button"
                  onClick={onRevision}
                  disabled={busy}
                  className="min-h-11 rounded border border-amber-600 px-4 py-3 text-sm text-amber-800 disabled:opacity-50"
                >
                  Tạo bản sửa
                </button>
              )}
              <button
                type="button"
                onClick={() => onExport("pyc", "xlsx")}
                disabled={busy}
                className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
              >
                PYC Excel
              </button>
              <button
                type="button"
                onClick={() => onExport("pyc", "pdf")}
                disabled={busy}
                className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
              >
                PYC PDF
              </button>
              <button
                type="button"
                onClick={() => onExport("bbnt", "xlsx")}
                disabled={busy || draft.status !== "confirmed"}
                title={
                  draft.status !== "confirmed"
                    ? "BBNT phải được người có quyền xác nhận trước khi xuất"
                    : undefined
                }
                className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
              >
                BBNT Excel
              </button>
              <button
                type="button"
                onClick={() => onExport("bbnt", "pdf")}
                disabled={busy || draft.status !== "confirmed"}
                title={
                  draft.status !== "confirmed"
                    ? "BBNT phải được người có quyền xác nhận trước khi xuất"
                    : undefined
                }
                className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
              >
                BBNT PDF
              </button>
            </div>
          </details>
        </div>

        {draft.status !== "confirmed" && !draft.id && (
          <p className="text-sm text-slate-600">
            Lưu nháp trước, sau đó người có quyền mới có thể xác nhận.
          </p>
        )}
      </div>
    </div>
  );
}
