import MenuButton from "../../../ui/MenuButton";
import RequestForm from "../components/RequestForm";
import { latestRequestForPrefill } from "../lib/requestPrefill";
import { requestStatusLabel } from "../lib/statusLabels";
import {
  buildWhatsAppInvite,
  whatsAppInviteUrl,
} from "../lib/whatsappInvite";
import {
  dailyReportLabel,
  recordActionLabel,
  requestSubtitle,
} from "./acceptancePageModel";
import type {
  AcceptanceRecord,
  AcceptanceRequest,
  LinkedDailyReport,
  ParticipantProfile,
  ProjectContext,
  RequestInput,
  WorkItemSummary,
} from "../types";

type Props = {
  projectId: string;
  requests: AcceptanceRequest[];
  projectContext: ProjectContext | null;
  profiles: ParticipantProfile[];
  workItems: WorkItemSummary[];
  reportLinks: Record<string, LinkedDailyReport | null>;
  editingRequest: AcceptanceRequest | "new" | null;
  selectedRequest: AcceptanceRequest | null;
  message: string | null;
  busy: boolean;
  previewBusy: boolean;
  recordFor: (requestId: string) => AcceptanceRecord | undefined;
  onSave: (input: RequestInput) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  onCancelEdit: () => void;
  onStartNew: () => void;
  onStartRecord: (request: AcceptanceRequest) => void;
  onStartEdit: (request: AcceptanceRequest) => void;
  onPreview: (request: AcceptanceRequest) => void;
  onExport: (request: AcceptanceRequest, format: "xlsx" | "pdf") => void;
  onCopyInvite: (request: AcceptanceRequest) => void;
  onDelete: (request: AcceptanceRequest) => void;
};

export default function RequestsPanel({
  projectId,
  requests,
  projectContext,
  profiles,
  workItems,
  reportLinks,
  editingRequest,
  selectedRequest,
  message,
  busy,
  previewBusy,
  recordFor,
  onSave,
  onDirtyChange,
  onCancelEdit,
  onStartNew,
  onStartRecord,
  onStartEdit,
  onPreview,
  onExport,
  onCopyInvite,
  onDelete,
}: Props) {
  return (
    <div className="space-y-4">
      {editingRequest ? (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <RequestForm
            projectId={projectId}
            project={projectContext}
            initial={selectedRequest}
            previousRequest={
              editingRequest === "new"
                ? latestRequestForPrefill(requests)
                : null
            }
            dailyReport={
              selectedRequest
                ? reportLinks[selectedRequest.id] ?? null
                : null
            }
            profiles={profiles}
            workItems={workItems}
            submitting={busy}
            onSubmit={onSave}
            onDirtyChange={onDirtyChange}
            onCancel={onCancelEdit}
          />
        </div>
      ) : (
        <div className="space-y-1">
          <button
            type="button"
            onClick={onStartNew}
            className="min-h-11 rounded bg-teal-700 px-4 py-3 font-semibold text-white"
          >
            + Tạo PYC nháp
          </button>
          {requests.length === 0 && (
            <p className="text-sm text-slate-600">Chưa có PYC. Tạo phiếu đầu tiên ở trên.</p>
          )}
        </div>
      )}

      {message && !editingRequest && (
        <p
          role="status"
          className="sticky bottom-[4.75rem] z-20 rounded bg-emerald-50 p-3 text-sm text-emerald-900 shadow-sm"
        >
          {message}
        </p>
      )}

      {requests.length > 0 && (
        <section className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-2 font-semibold">Danh sách PYC</h2>
          <ul className="divide-y">
            {requests.map((request) => {
              const record = recordFor(request.id);
              return (
                <li key={request.id} className="flex flex-wrap items-center gap-2 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      PYC {request.number}{" "}
                      <span className="text-sm text-slate-600">
                        ({requestStatusLabel(request.status)})
                      </span>
                    </p>
                    <p className="truncate text-sm text-slate-600">
                      {requestSubtitle(request)}
                    </p>
                    {request.daily_report_id && (
                      <p className="text-sm text-teal-800">
                        Báo cáo ngày:{" "}
                        {dailyReportLabel(reportLinks[request.id])}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => onStartRecord(request)}
                    className="min-h-11 rounded bg-teal-700 px-4 py-2 text-sm font-semibold text-white"
                  >
                    {recordActionLabel(record)}
                  </button>
                  <MenuButton
                    label="Thao tác"
                    triggerClassName="min-h-11 cursor-pointer rounded border px-4 py-2 text-sm"
                    panelClassName="right-0 w-48 rounded border bg-white p-1 shadow-lg"
                  >
                    <button
                      type="button"
                      onClick={() => onStartEdit(request)}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50"
                    >
                      Sửa PYC
                    </button>
                    <button
                      type="button"
                      onClick={() => onPreview(request)}
                      disabled={busy || previewBusy}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      {previewBusy ? "Đang tạo ảnh xem trước…" : "Xem trước"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onExport(request, "xlsx")}
                      disabled={busy}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      PYC Excel
                    </button>
                    <button
                      type="button"
                      onClick={() => onExport(request, "pdf")}
                      disabled={busy}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      PYC PDF
                    </button>
                    <button
                      type="button"
                      onClick={() => onCopyInvite(request)}
                      disabled={busy}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      Copy lời mời WhatsApp
                    </button>
                    <a
                      href={whatsAppInviteUrl(buildWhatsAppInvite(request))}
                      target="_blank"
                      rel="noreferrer"
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50"
                    >
                      Mở WhatsApp
                    </a>
                    <button
                      type="button"
                      onClick={() => onDelete(request)}
                      disabled={busy}
                      className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                    >
                      Xoá PYC
                    </button>
                  </MenuButton>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
