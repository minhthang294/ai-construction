import { useEffect, useRef, useState } from "react";
import ConfirmDialog from "../components/ConfirmDialog";
import {
  confirmRecord,
  createRecord,
  createRecordRevision,
  createRequest,
  deleteRequest,
  updateRecord,
  updateRequest,
} from "../lib/api";
import { buildWhatsAppInvite } from "../lib/whatsappInvite";
import type {
  AcceptanceExport,
  AcceptanceNavigationPayload,
  AcceptanceRecord,
  AcceptanceRequest,
  RecordInput,
  RequestInput,
  ResultState,
} from "../types";
import AcceptanceHeader from "./AcceptanceHeader";
import AcceptanceNotices from "./AcceptanceNotices";
import AcceptanceSettings from "./AcceptanceSettings";
import {
  deleteRequestWarning,
  draftFor,
  draftPayload,
  errorMessage,
} from "./acceptancePageModel";
import type { RecordDraft, Tab } from "./acceptancePageModel";
import PendingAcceptancePanel from "./PendingAcceptancePanel";
import RecordsPanel from "./RecordsPanel";
import RequestsPanel from "./RequestsPanel";
import { useAcceptanceData } from "./useAcceptanceData";
import { useAcceptanceExport } from "./useAcceptanceExport";
import { useAcceptanceNavigation } from "./useAcceptanceNavigation";
import { useAcceptancePending } from "./useAcceptancePending";
import { useAcceptancePreview } from "./useAcceptancePreview";

type Props = {
  projectId: string;
  onDirtyChange?: (dirty: boolean) => void;
  /**
   * App-level navigation payload from the site paste flow.  The app shell owns
   * the type in ``frontend/src/app``; this page reads it through this prop.
   */
  initialState?: AcceptanceNavigationPayload | null;
};

export default function AcceptancePage({
  projectId,
  onDirtyChange,
  initialState,
}: Props) {
  const [tab, setTab] = useState<Tab>("requests");
  const [editingRequest, setEditingRequest] = useState<AcceptanceRequest | "new" | null>(null);
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastExport, setLastExport] = useState<AcceptanceExport | null>(null);
  const [downloadFailed, setDownloadFailed] = useState(false);
  const [requestDirty, setRequestDirty] = useState(false);
  const [recordDirty, setRecordDirty] = useState(false);
  const onDirtyChangeRef = useRef(onDirtyChange);

  useEffect(() => {
    onDirtyChangeRef.current = onDirtyChange;
    onDirtyChange?.(requestDirty || recordDirty);
  }, [onDirtyChange]);

  useEffect(() => {
    onDirtyChangeRef.current?.(requestDirty || recordDirty);
  }, [requestDirty, recordDirty]);

  const {
    preview,
    previewImageUrl,
    previewBusy,
    closePreview,
    previewRequestById,
    previewRecordById,
  } = useAcceptancePreview({ projectId, setError });

  const {
    requests,
    records,
    profiles,
    workItems,
    projectContext,
    reportLinks,
    refresh,
    recordFor,
    setProfiles,
    setRecords,
  } = useAcceptanceData({
    projectId,
    setError,
    onProjectChange: () => {
      setDraft(null);
      setEditingRequest(null);
      setLastExport(null);
      closePreview();
      setRequestDirty(false);
      setRecordDirty(false);
    },
  });

  const {
    pending,
    pendingSelected,
    pendingBusy,
    pendingFilterActive,
    pendingTotalAll,
    loadPending,
    clearPendingFilter,
    togglePending,
    createPendingRequest,
  } = useAcceptancePending({
    projectId,
    initialState,
    refresh,
    onCreated: (request) => {
      setTab("requests");
      setEditingRequest(request);
    },
    setMessage,
    setError,
  });

  const {
    loadDraft,
    updateDraft,
    switchTab,
    closeRequestEditor,
    closeRecordEditor,
    startEditRequest,
    openRequestById,
    openRecordById,
    startRecord,
  } = useAcceptanceNavigation({
    requests,
    records,
    projectContext,
    recordFor,
    refresh,
    closePreview,
    tab,
    setTab,
    editingRequest,
    setEditingRequest,
    draft,
    setDraft,
    requestDirty,
    setRequestDirty,
    recordDirty,
    setRecordDirty,
    setConfirming,
    setMessage,
    setError,
  });

  const { handleExportRequest, handleExportRecord, handleDownloadExport } =
    useAcceptanceExport({
      projectId,
      draftId: draft?.id,
      setLastExport,
      setDownloadFailed,
      setBusy,
      setError,
      setMessage,
    });

  useEffect(() => {
    return () => {
      onDirtyChangeRef.current?.(false);
    };
  }, [projectId]);

  async function saveRequest(input: RequestInput): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      let saved: AcceptanceRequest;
      if (editingRequest && editingRequest !== "new") {
        saved = await updateRequest(projectId, editingRequest.id, input);
        setMessage(`Đã cập nhật PYC ${saved.number}.`);
      } else {
        saved = await createRequest(projectId, input);
        setMessage(`Đã tạo PYC nháp ${saved.number}.`);
      }
      if (saved.excel_sync_warning) {
        setMessage((current) =>
          current
            ? `${current} ${saved.excel_sync_warning}`
            : saved.excel_sync_warning ?? null,
        );
      }
      setEditingRequest(null);
      setRequestDirty(false);
      await refresh();
      return true;
    } catch (cause) {
      setError(errorMessage(cause));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveRecord() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const payload = draftPayload(draft);
      let saved: AcceptanceRecord;
      if (draft.id) {
        const { request_id: _requestId, ...update } = payload;
        saved = await updateRecord(projectId, draft.id, update);
      } else {
        saved = await createRecord(projectId, payload);
      }
      const { requestList, recordList } = await refresh();
      const request = requestList.find((item) => item.id === saved.request_id);
      loadDraft(draftFor(saved, request, projectContext));
      setRecords(recordList);
      setMessage(
        saved.status === "confirmed"
          ? "BBNT đã được xác nhận."
          : `Đã lưu BBNT nháp${request ? ` cho PYC ${request.number}` : ""}.`,
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(result: ResultState, note: string) {
    if (!draft?.id) throw new Error("Cần lưu BBNT trước khi xác nhận.");
    setBusy(true);
    setError(null);
    try {
      const confirmed = await confirmRecord(projectId, draft.id, {
        result,
        conclusion_note: note || null,
      });
      const { requestList, recordList } = await refresh();
      const request = requestList.find((item) => item.id === confirmed.request_id);
      loadDraft(draftFor(confirmed, request, projectContext));
      setRecords(recordList);
      await loadPending();
      setConfirming(false);
      setMessage("Đã ghi nhận xác nhận của người có quyền.");
    } catch (cause) {
      setError(errorMessage(cause));
      throw cause;
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyInvite(request: AcceptanceRequest) {
    const invite = buildWhatsAppInvite(request);
    try {
      await navigator.clipboard.writeText(invite);
      setError(null);
      setMessage("Đã copy lời mời WhatsApp.");
    } catch {
      setError(null);
      window.prompt("Sao chép lời mời WhatsApp", invite);
    }
  }

  async function handleDeleteRequest(request: AcceptanceRequest) {
    if (busy) return;
    const record = recordFor(request.id);
    const warning = deleteRequestWarning(request, record);
    if (!window.confirm(warning)) return;

    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await deleteRequest(projectId, request.id, Boolean(record));
      if (
        editingRequest &&
        editingRequest !== "new" &&
        editingRequest.id === request.id
      ) {
        setEditingRequest(null);
        setRequestDirty(false);
      }
      if (draft?.request_id === request.id) {
        setDraft(null);
        setRecordDirty(false);
        setConfirming(false);
      }
      closePreview();
      await refresh();
      setMessage(`Đã xoá PYC ${request.number}.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevision() {
    if (!draft?.id) return;
    if (
      !window.confirm(
        "Tạo bản sửa mới từ bản hiện tại? Bản cũ sẽ được giữ nguyên và bản sửa mới ở trạng thái nháp.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const revised = await createRecordRevision(projectId, draft.id);
      const { requestList, recordList } = await refresh();
      const request = requestList.find((item) => item.id === revised.request_id);
      loadDraft(draftFor(revised, request, projectContext));
      setRecords(recordList);
      closePreview();
      setMessage(`Đã tạo bản sửa ${revised.revision}; bản cũ được giữ nguyên.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const selectedRequest = editingRequest && editingRequest !== "new" ? editingRequest : null;

  return (
    <div className="space-y-4">
      <AcceptanceHeader tab={tab} onSwitchTab={switchTab} />

      {pending && (pending.total_components > 0 || pendingFilterActive) && (
        <PendingAcceptancePanel
          pending={pending}
          pendingFilterActive={pendingFilterActive}
          pendingTotalAll={pendingTotalAll}
          pendingSelected={pendingSelected}
          pendingBusy={pendingBusy}
          onClearFilter={() => void clearPendingFilter()}
          onToggle={togglePending}
          onCreate={() => void createPendingRequest()}
        />
      )}

      <AcceptanceNotices
        error={error}
        showError={!editingRequest && !draft}
        lastExport={lastExport}
        downloadFailed={downloadFailed}
        busy={busy}
        onDownloadExport={handleDownloadExport}
        preview={preview}
        previewImageUrl={previewImageUrl}
        previewBusy={previewBusy}
        onClosePreview={closePreview}
      />

      {tab === "requests" && (
        <RequestsPanel
          projectId={projectId}
          requests={requests}
          projectContext={projectContext}
          profiles={profiles}
          workItems={workItems}
          reportLinks={reportLinks}
          editingRequest={editingRequest}
          selectedRequest={selectedRequest}
          message={message}
          busy={busy}
          previewBusy={previewBusy}
          recordFor={recordFor}
          onSave={saveRequest}
          onDirtyChange={setRequestDirty}
          onCancelEdit={closeRequestEditor}
          onStartNew={() => setEditingRequest("new")}
          onStartRecord={startRecord}
          onStartEdit={startEditRequest}
          onPreview={(request) => void previewRequestById(request)}
          onExport={(request, format) => void handleExportRequest(request, format)}
          onCopyInvite={(request) => void handleCopyInvite(request)}
          onDelete={(request) => void handleDeleteRequest(request)}
        />
      )}

      {tab === "records" && (
        <RecordsPanel
          projectId={projectId}
          requests={requests}
          draft={draft}
          message={message}
          error={error}
          busy={busy}
          reportLinks={reportLinks}
          recordFor={recordFor}
          onStartRecord={startRecord}
          onUpdateDraft={updateDraft}
          onSave={() => void saveRecord()}
          onClose={closeRecordEditor}
          onConfirm={() => setConfirming(true)}
          onPreview={() => void previewRecordById(draft?.id)}
          onRevision={() => void handleRevision()}
          onExport={(kind, format) => void handleExportRecord(kind, format)}
        />
      )}

      <AcceptanceSettings
        projectId={projectId}
        onProfilesChanged={setProfiles}
        onRefresh={() => void refresh()}
        onOpenRequest={(requestId) => void openRequestById(requestId)}
        onOpenRecord={(recordId) => void openRecordById(recordId)}
      />

      {draft && confirming && draft.id && (
        (() => {
          const serverRecord = records.find((record) => record.id === draft.id);
          if (!serverRecord) return null;
          return (
            <ConfirmDialog
              record={serverRecord}
              open={confirming}
              submitting={busy}
              onCancel={() => setConfirming(false)}
              onConfirm={handleConfirm}
            />
          );
        })()
      )}
    </div>
  );
}
