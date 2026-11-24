import type { Dispatch, SetStateAction } from "react";
import { DISCARD_MESSAGE, requiresDiscardConfirmation } from "../lib/formGuard";
import type { GuardTarget } from "../lib/formGuard";
import { draftFor, newDraft } from "./acceptancePageModel";
import type { RecordDraft, Tab } from "./acceptancePageModel";
import type { AcceptanceRecord, AcceptanceRequest, ProjectContext } from "../types";

type Options = {
  requests: AcceptanceRequest[];
  records: AcceptanceRecord[];
  projectContext: ProjectContext | null;
  recordFor: (requestId: string) => AcceptanceRecord | undefined;
  refresh: () => Promise<{
    requestList: AcceptanceRequest[];
    recordList: AcceptanceRecord[];
  }>;
  closePreview: () => void;
  tab: Tab;
  setTab: Dispatch<SetStateAction<Tab>>;
  editingRequest: AcceptanceRequest | "new" | null;
  setEditingRequest: Dispatch<
    SetStateAction<AcceptanceRequest | "new" | null>
  >;
  draft: RecordDraft | null;
  setDraft: Dispatch<SetStateAction<RecordDraft | null>>;
  requestDirty: boolean;
  setRequestDirty: Dispatch<SetStateAction<boolean>>;
  recordDirty: boolean;
  setRecordDirty: Dispatch<SetStateAction<boolean>>;
  setConfirming: Dispatch<SetStateAction<boolean>>;
  setMessage: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
};

export function useAcceptanceNavigation({
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
}: Options) {
  function confirmDiscard(target: GuardTarget): boolean {
    const snapshot = {
      tab,
      requestDirty,
      recordDirty,
      hasEditingRequest: Boolean(editingRequest),
      hasDraft: Boolean(draft),
    };
    if (!requiresDiscardConfirmation(snapshot, target)) return true;
    return window.confirm(DISCARD_MESSAGE);
  }

  function loadDraft(next: RecordDraft | null) {
    setDraft(next);
    setRecordDirty(false);
  }

  function updateDraft(updater: (current: RecordDraft) => RecordDraft) {
    setDraft((current) => (current ? updater(current) : current));
    setRecordDirty(true);
  }

  function switchTab(next: Tab) {
    if (next === tab) return;
    if (!confirmDiscard({ type: "switch-tab", tab: next })) return;
    if (tab === "requests") {
      setEditingRequest(null);
      setRequestDirty(false);
    } else {
      setDraft(null);
      setRecordDirty(false);
    }
    closePreview();
    setTab(next);
  }

  function closeRequestEditor() {
    if (!confirmDiscard({ type: "close-request" })) return;
    setEditingRequest(null);
    setRequestDirty(false);
  }

  function closeRecordEditor() {
    if (!confirmDiscard({ type: "close-record" })) return;
    setConfirming(false);
    setDraft(null);
    setRecordDirty(false);
  }

  function startEditRequest(request: AcceptanceRequest) {
    if (editingRequest === request) {
      setTab("requests");
      return;
    }
    if (tab === "records" && !confirmDiscard({ type: "switch-tab", tab: "requests" })) {
      return;
    }
    if (!confirmDiscard({ type: "edit-request" })) return;
    if (tab === "records") {
      setDraft(null);
      setRecordDirty(false);
    }
    setRequestDirty(false);
    closePreview();
    setTab("requests");
    setEditingRequest(request);
  }

  async function openRequestById(requestId: string) {
    let request = requests.find((item) => item.id === requestId);
    if (!request) {
      const { requestList } = await refresh();
      request = requestList.find((item) => item.id === requestId);
    }
    if (!request) {
      setMessage("Không tìm thấy PYC trong danh sách hiện tại.");
      return;
    }
    if (tab === "records" && !confirmDiscard({ type: "switch-tab", tab: "requests" })) {
      return;
    }
    if (tab === "requests" && editingRequest !== request && !confirmDiscard({ type: "edit-request" })) {
      return;
    }
    if (tab === "records") {
      setDraft(null);
      setRecordDirty(false);
    }
    closePreview();
    setTab("requests");
    setRequestDirty(false);
    setEditingRequest(request);
  }

  async function openRecordById(recordId: string) {
    let record = records.find((item) => item.id === recordId);
    let request = record
      ? requests.find((item) => item.id === record?.request_id)
      : undefined;
    if (!record) {
      const { recordList, requestList } = await refresh();
      record = recordList.find((item) => item.id === recordId);
      request = requestList.find((item) => item.id === record?.request_id);
    }
    if (!record) {
      setMessage("Không tìm thấy BBNT trong danh sách hiện tại.");
      return;
    }
    if (tab === "requests" && !confirmDiscard({ type: "switch-tab", tab: "records" })) {
      return;
    }
    if (tab === "records" && draft && !confirmDiscard({ type: "close-record" })) {
      return;
    }
    if (tab === "requests") {
      setEditingRequest(null);
      setRequestDirty(false);
    }
    closePreview();
    setTab("records");
    loadDraft(draftFor(record, request, projectContext));
  }

  function startRecord(request: AcceptanceRequest) {
    if (tab === "records" && draft && !confirmDiscard({ type: "close-record" })) {
      return;
    }
    if (tab === "requests" && !confirmDiscard({ type: "switch-tab", tab: "records" })) {
      return;
    }
    if (tab === "requests" && requestDirty) {
      setEditingRequest(null);
      setRequestDirty(false);
    }
    const existing = recordFor(request.id);
    setError(null);
    setMessage(null);
    setTab("records");
    if (existing) {
      if (existing.status === "confirmed") {
        setMessage("BBNT đã được xác nhận và chỉ được xem/xuất.");
      }
      loadDraft(draftFor(existing, request, projectContext));
    } else {
      loadDraft(newDraft(request, projectContext));
    }
  }

  return {
    loadDraft,
    updateDraft,
    switchTab,
    closeRequestEditor,
    closeRecordEditor,
    startEditRequest,
    openRequestById,
    openRecordById,
    startRecord,
  };
}
