import { useEffect, useRef, useState } from "react";
import AcceptanceHistoryPanel from "../components/AcceptanceHistoryPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import NumberingPanel from "../components/NumberingPanel";
import ParticipantLibrary from "../components/ParticipantLibrary";
import ParticipantsEditor from "../components/ParticipantsEditor";
import RequestForm from "../components/RequestForm";
import TriStateChecklist from "../components/TriStateChecklist";
import {
  AcceptanceApiError,
  createRecord,
  createRecordRevision,
  createRequest,
  downloadExport,
  exportRecord,
  exportRequest,
  getProjectContext,
  getRequestDailyReport,
  listParticipantProfiles,
  listRecords,
  listRequests,
  previewRecord,
  previewRequest,
  updateRecord,
  updateRequest,
} from "../lib/api";
import { projectMetadataDefaults } from "../lib/projectPrefill";
import { confirmRecord } from "../lib/api";
import type {
  AcceptanceExport,
  AcceptanceRecord,
  AcceptanceRequest,
  ChecklistInput,
  LinkedDailyReport,
  ParticipantInput,
  ParticipantProfile,
  PreviewPayload,
  ProjectContext,
  RecordInput,
  RequestInput,
  ResultState,
  YesNo,
} from "../types";
import { emptyChecklist } from "../types";
import {
  DISCARD_MESSAGE,
  requiresDiscardConfirmation,
  shouldOfferRevision,
  type GuardTarget,
} from "../lib/formGuard";

type Props = {
  projectId: string;
  onDirtyChange?: (dirty: boolean) => void;
};

type Tab = "requests" | "records";

type RecordDraft = {
  id?: string;
  request_id: string;
  request_number?: string;
  project_name: string;
  client: string;
  project_location: string;
  location: string;
  number?: string | null;
  revision: number;
  stale: boolean;
  stale_warning?: string | null;
  status: "draft" | "confirmed";
  record_date: string;
  start_time: string;
  end_time: string;
  design_compliance: YesNo | "";
  technical_compliance: YesNo | "";
  other_notes: string;
  conclusion_note: string;
  result?: ResultState | null;
  participants: ParticipantInput[];
  checklist: ChecklistInput[];
};

function today(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function draftFor(
  record: AcceptanceRecord,
  request?: AcceptanceRequest,
  project?: ProjectContext | null,
): RecordDraft {
  const metadata = projectMetadataDefaults(project);
  return {
    id: record.id,
    request_id: record.request_id,
    request_number: request?.number,
    project_name: request?.project_name || metadata.project_name,
    client: request?.client || metadata.client,
    project_location: request?.project_location || metadata.project_location,
    location: request?.location ?? "",
    number: record.number,
    revision: record.revision,
    stale: record.stale,
    stale_warning: record.stale_warning,
    status: record.status,
    record_date: record.record_date ?? "",
    start_time: record.start_time ?? "",
    end_time: record.end_time ?? "",
    design_compliance: record.design_compliance ?? "",
    technical_compliance: record.technical_compliance ?? "",
    other_notes: record.other_notes ?? "",
    conclusion_note: record.conclusion_note ?? "",
    result: record.result,
    participants: record.participants.map((participant) => ({
      role: participant.role,
      person_name: participant.person_name,
      organization: participant.organization ?? "",
      position: participant.position ?? "",
      sort_order: participant.sort_order,
    })),
    checklist: record.checklist.map((item) => ({
      item: item.item,
      state: item.state,
      evidence_refs: item.evidence_refs,
      note: item.note ?? undefined,
      sort_order: item.sort_order,
    })),
  };
}

function newDraft(
  request: AcceptanceRequest,
  project?: ProjectContext | null,
): RecordDraft {
  const metadata = projectMetadataDefaults(project);
  return {
    request_id: request.id,
    request_number: request.number,
    project_name: request.project_name || metadata.project_name,
    client: request.client || metadata.client,
    project_location: request.project_location || metadata.project_location,
    location: request.location ?? "",
    number: null,
    revision: 1,
    stale: false,
    stale_warning: null,
    status: "draft",
    record_date: today(),
    start_time: "",
    end_time: "",
    design_compliance: "",
    technical_compliance: "",
    other_notes: "",
    conclusion_note: "",
    result: null,
    // Deliberately empty: never reuse old personnel from the template.
    participants: [],
    checklist: emptyChecklist(),
  };
}

function draftPayload(draft: RecordDraft): RecordInput {
  const participants = draft.participants
    .filter((participant) => participant.person_name.trim())
    .map((participant, index) => ({
      ...participant,
      person_name: participant.person_name.trim(),
      sort_order: index,
    }));
  const payload: RecordInput = {
    request_id: draft.request_id,
    number: draft.number ?? null,
    record_date: draft.record_date || null,
    start_time: draft.start_time.trim() || null,
    end_time: draft.end_time.trim() || null,
    design_compliance: draft.design_compliance || null,
    technical_compliance: draft.technical_compliance || null,
    other_notes: draft.other_notes.trim() || null,
    conclusion_note: draft.conclusion_note.trim() || null,
    checklist: draft.checklist,
  };
  // On the first save, omit an empty list so the backend can prefill from PYC.
  if (draft.id || participants.length > 0) payload.participants = participants;
  return payload;
}

function errorMessage(error: unknown): string {
  if (error instanceof AcceptanceApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return error instanceof Error ? error.message : "Thao tác thất bại.";
}

export default function AcceptancePage({ projectId, onDirtyChange }: Props) {
  const [tab, setTab] = useState<Tab>("requests");
  const [requests, setRequests] = useState<AcceptanceRequest[]>([]);
  const [records, setRecords] = useState<AcceptanceRecord[]>([]);
  const [editingRequest, setEditingRequest] = useState<AcceptanceRequest | "new" | null>(null);
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastExport, setLastExport] = useState<AcceptanceExport | null>(null);
  const [reportLinks, setReportLinks] = useState<
    Record<string, LinkedDailyReport | null>
  >({});
  const [profiles, setProfiles] = useState<ParticipantProfile[]>([]);
  const [projectContext, setProjectContext] = useState<ProjectContext | null>(null);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
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

  useEffect(() => {
    return () => {
      onDirtyChangeRef.current?.(false);
    };
  }, [projectId]);

  async function refresh() {
    const [requestList, recordList] = await Promise.all([
      listRequests(projectId),
      listRecords(projectId),
    ]);
    setRequests(requestList);
    setRecords(recordList);
    return { requestList, recordList };
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [requestList, recordList, profileList, project] = await Promise.all([
          listRequests(projectId),
          listRecords(projectId),
          listParticipantProfiles(projectId),
          getProjectContext(projectId).catch(() => null),
        ]);
        if (!active) return;
        setRequests(requestList);
        setRecords(recordList);
        setProfiles(profileList);
        setProjectContext(project);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    })();
    setDraft(null);
    setEditingRequest(null);
    setLastExport(null);
    setPreview(null);
    setProjectContext(null);
    setRequestDirty(false);
    setRecordDirty(false);
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    const linked = requests.filter((request) => request.daily_report_id);
    if (linked.length === 0) {
      setReportLinks({});
      return;
    }
    Promise.all(
      linked.map(async (request) => {
        try {
          const report = await getRequestDailyReport(projectId, request.id);
          return [request.id, report] as const;
        } catch {
          return [request.id, null] as const;
        }
      }),
    ).then((entries) => {
      if (active) setReportLinks(Object.fromEntries(entries));
    });
    return () => {
      active = false;
    };
  }, [projectId, requests]);

  function recordFor(requestId: string): AcceptanceRecord | undefined {
    return records.find((record) => record.request_id === requestId);
  }

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
    setPreview(null);
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
    setPreview(null);
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
    setPreview(null);
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
    setPreview(null);
    setTab("records");
    loadDraft(draftFor(record, request, projectContext));
  }

  async function saveRequest(input: RequestInput): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      if (editingRequest && editingRequest !== "new") {
        await updateRequest(projectId, editingRequest.id, input);
        setMessage(`Đã cập nhật PYC ${input.number}.`);
      } else {
        await createRequest(projectId, input);
        setMessage(`Đã tạo PYC nháp ${input.number}.`);
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
      setConfirming(false);
      setMessage("Đã ghi nhận xác nhận của người có quyền.");
    } catch (cause) {
      setError(errorMessage(cause));
      throw cause;
    } finally {
      setBusy(false);
    }
  }

  async function handleExportRequest(request: AcceptanceRequest, format: "xlsx" | "pdf") {
    setBusy(true);
    setError(null);
    try {
      const exported = await exportRequest(projectId, request.id, format);
      setLastExport(exported);
      setMessage(
        `Đã tạo ${format.toUpperCase()} PYC ${request.number}. Chỉ các ô đã kiểm tra được ghi.`,
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewRequest(request: AcceptanceRequest) {
    setError(null);
    try {
      setPreview(await previewRequest(projectId, request.id));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  async function handlePreviewRecord() {
    if (!draft?.id) {
      setError("Cần lưu BBNT trước khi xem trước.");
      return;
    }
    setError(null);
    try {
      setPreview(await previewRecord(projectId, draft.id));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  async function handleRevision() {
    if (!draft?.id) return;
    if (
      !window.confirm(
        "Tạo revision mới từ bản hiện tại? Bản cũ sẽ được giữ nguyên và revision mới ở trạng thái nháp.",
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
      setPreview(null);
      setMessage(`Đã tạo revision ${revised.revision}; bản cũ được giữ nguyên.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleExportRecord(kind: "pyc" | "bbnt", format: "xlsx" | "pdf") {
    if (!draft?.id) {
      setError("Cần lưu BBNT trước khi xuất.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const exported = await exportRecord(projectId, draft.id, kind, format);
      setLastExport(exported);
      setMessage(
        kind === "bbnt"
          ? `Đã tạo ${format.toUpperCase()} BBNT. Bản xuất dùng dữ liệu đã được con người xác nhận.`
          : `Đã tạo ${format.toUpperCase()} PYC từ BBNT; sheet BBNT được để trống an toàn.`,
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadExport(exported: AcceptanceExport) {
    setBusy(true);
    setError(null);
    try {
      const filename = await downloadExport(exported);
      setMessage(`Đã tải ${filename}.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const selectedRequest = editingRequest && editingRequest !== "new" ? editingRequest : null;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Nghiệm thu (PYC / BBNT)</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => switchTab("requests")}
            className={`rounded px-3 py-2 text-sm ${tab === "requests" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Phiếu yêu cầu (PYC)
          </button>
          <button
            type="button"
            onClick={() => switchTab("records")}
            className={`rounded px-3 py-2 text-sm ${tab === "records" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Biên bản nghiệm thu (BBNT)
          </button>
        </div>
      </header>

      {message && <div className="rounded bg-emerald-50 p-3 text-sm text-emerald-900">{message}</div>}
      {error && (
        <div role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-900">
          {error}
        </div>
      )}
      {lastExport && (
        <div className="rounded bg-white p-3 text-sm shadow-sm">
          File đã tạo:{" "}
          <button
            type="button"
            className="inline-flex min-h-11 items-center text-teal-700 underline disabled:opacity-50"
            disabled={busy}
            onClick={() => void handleDownloadExport(lastExport)}
          >
            tải {lastExport.kind.toUpperCase()} (.{lastExport.format})
          </button>{" "}
          <span className="text-slate-500">sha256 {lastExport.sha256.slice(0, 12)}…</span>
        </div>
      )}

      {preview && (
        <section className="rounded-xl bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Xem trước {preview.kind.toUpperCase()}</h2>
            <button type="button" className="text-sm underline" onClick={() => setPreview(null)}>
              Đóng
            </button>
          </div>
          {preview.warnings.map((warning) => (
            <p key={warning} className="mt-2 rounded bg-amber-50 p-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">
            {JSON.stringify(preview.cells, null, 2)}
          </pre>
        </section>
      )}

      {tab === "requests" && (
        <div className="space-y-4">
          {editingRequest ? (
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <RequestForm
                projectId={projectId}
                project={projectContext}
                initial={selectedRequest}
                dailyReport={
                  selectedRequest
                    ? reportLinks[selectedRequest.id] ?? null
                    : null
                }
                profiles={profiles}
                submitting={busy}
                onSubmit={saveRequest}
                onDirtyChange={setRequestDirty}
                onCancel={closeRequestEditor}
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setEditingRequest("new")}
              className="rounded bg-teal-700 px-4 py-3 font-semibold text-white"
            >
              + Tạo PYC nháp
            </button>
          )}

          <section className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="mb-2 font-semibold">Danh sách PYC</h2>
            {requests.length === 0 && <p className="text-sm text-slate-500">Chưa có PYC.</p>}
            <ul className="divide-y">
              {requests.map((request) => {
                const record = recordFor(request.id);
                return (
                  <li key={request.id} className="flex flex-wrap items-center gap-2 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        PYC {request.number}{" "}
                        <span className="text-xs text-slate-500">({request.status})</span>
                      </p>
                      <p className="truncate text-sm text-slate-600">
                        {request.location || request.subject || request.project_name || "Chưa có nội dung"}
                      </p>
                      {request.daily_report_id && (
                        <p className="text-xs text-teal-800">
                          Báo cáo ngày:{" "}
                          {reportLinks[request.id]
                            ? `${reportLinks[request.id]?.report_date} (${reportLinks[request.id]?.status})`
                            : "đã liên kết"}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => startRecord(request)}
                      className="min-h-11 rounded bg-teal-700 px-4 py-2 text-sm font-semibold text-white"
                    >
                      {record ? "Mở BBNT" : "Tạo BBNT"}
                    </button>
                    <details className="relative">
                      <summary className="min-h-11 cursor-pointer list-none rounded border px-4 py-2 text-sm [&::-webkit-details-marker]:hidden">
                        Thao tác
                      </summary>
                      <div className="absolute right-0 z-10 mt-1 w-48 rounded border bg-white p-1 shadow-lg">
                        <button
                          type="button"
                          onClick={() => startEditRequest(request)}
                          className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50"
                        >
                          Sửa PYC
                        </button>
                        <button
                          type="button"
                          onClick={() => void handlePreviewRequest(request)}
                          className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50"
                        >
                          Xem trước
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleExportRequest(request, "xlsx")}
                          disabled={busy}
                          className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                        >
                          PYC Excel
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleExportRequest(request, "pdf")}
                          disabled={busy}
                          className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                        >
                          PYC PDF
                        </button>
                      </div>
                    </details>
                  </li>
                );
              })}
            </ul>
          </section>
          <ParticipantLibrary projectId={projectId} onChanged={setProfiles} />
        </div>
      )}

      {tab === "records" && (
        <div className="space-y-4">
          {!draft && (
            <section className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-2 font-semibold">Chọn PYC để lập BBNT</h2>
              {requests.length === 0 && <p className="text-sm text-slate-500">Chưa có PYC.</p>}
              <ul className="divide-y">
                {requests.map((request) => {
                  const record = recordFor(request.id);
                  return (
                    <li key={request.id} className="flex items-center gap-2 py-3">
                      <span className="flex-1">
                        PYC {request.number} {record ? `— BBNT ${record.status}` : "— chưa có BBNT"}
                      </span>
                      <button
                        type="button"
                        onClick={() => startRecord(request)}
                        className="rounded border border-teal-700 px-3 py-2 text-sm text-teal-800"
                      >
                        {record ? "Mở" : "Lập BBNT"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {draft && (
            <div className="space-y-4 rounded-xl bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">
                  BBNT {draft.number ? `số ${draft.number}` : draft.request_number ? `cho PYC ${draft.request_number}` : "(nháp)"}{" "}
                  — revision {draft.revision}
                </h2>
                <span className="text-xs rounded bg-slate-100 px-2 py-1 text-slate-700">
                  {draft.status === "confirmed"
                    ? `Đã xác nhận: ${draft.result ?? ""}`
                    : "Nháp — chưa có kết luận"}
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
              <p className="text-xs text-slate-500">
                Thông tin công trình được lấy lại từ PYC/Thiết lập công trình; không cần nhập lại.
              </p>

              {reportLinks[draft.request_id] && (
                <div className="rounded bg-teal-50 p-2 text-sm text-teal-900">
                  Báo cáo ngày liên kết:{" "}
                  {reportLinks[draft.request_id]?.report_date} (
                  {reportLinks[draft.request_id]?.status}) —{" "}
                  <a
                    className="inline-flex min-h-11 items-center underline"
                    href={`/api/v1/projects/${projectId}/daily-reports/${reportLinks[draft.request_id]?.report_date}`}
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
                    onChange={(event) => updateDraft((current) => ({ ...current, record_date: event.target.value }))}
                  />
                </label>
                <label className="block text-sm">
                  Bắt đầu
                  <input
                    className="mt-1 w-full rounded border p-3"
                    value={draft.start_time}
                    placeholder="Ví dụ: 15h00"
                    disabled={draft.status === "confirmed"}
                    onChange={(event) => updateDraft((current) => ({ ...current, start_time: event.target.value }))}
                  />
                </label>
                <label className="block text-sm">
                  Kết thúc
                  <input
                    className="mt-1 w-full rounded border p-3"
                    value={draft.end_time}
                    placeholder="Ví dụ: 16h20"
                    disabled={draft.status === "confirmed"}
                    onChange={(event) => updateDraft((current) => ({ ...current, end_time: event.target.value }))}
                  />
                </label>
                <label className="block text-sm">
                  So với thiết kế
                  <select
                    className="mt-1 w-full rounded border p-3"
                    value={draft.design_compliance}
                    disabled={draft.status === "confirmed"}
                    onChange={(event) =>
                      updateDraft((current) => ({
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
                      updateDraft((current) => ({
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
                  onChange={(event) => updateDraft((current) => ({ ...current, other_notes: event.target.value }))}
                />
              </label>

              <ParticipantsEditor
                items={draft.participants}
                disabled={draft.status === "confirmed"}
                onChange={(participants) => updateDraft((current) => ({ ...current, participants }))}
              />

              <TriStateChecklist
                items={draft.checklist}
                disabled={draft.status === "confirmed"}
                onChange={(checklist) => updateDraft((current) => ({ ...current, checklist }))}
              />

              <label className="block text-sm">
                Ghi chú kết luận (chỉ người xác nhận ghi)
                <textarea
                  className="mt-1 w-full rounded border p-3"
                  rows={2}
                  value={draft.conclusion_note}
                  disabled={draft.status === "confirmed"}
                  onChange={(event) => updateDraft((current) => ({ ...current, conclusion_note: event.target.value }))}
                />
              </label>

              <div className="flex flex-wrap gap-2">
                {draft.status !== "confirmed" && (
                  <button
                    type="button"
                    onClick={saveRecord}
                    disabled={busy}
                    className="rounded bg-teal-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
                  >
                    {busy ? "Đang lưu..." : "Lưu BBNT nháp"}
                  </button>
                )}
                {draft.status !== "confirmed" && draft.id && (
                  <button
                    type="button"
                    onClick={() => setConfirming(true)}
                    disabled={busy}
                    className="rounded bg-emerald-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
                  >
                    Xác nhận BBNT
                  </button>
                )}
                {draft.id && (
                  <button
                    type="button"
                    onClick={handlePreviewRecord}
                    disabled={busy}
                    className="rounded border px-4 py-3 disabled:opacity-50"
                  >
                    Xem trước
                  </button>
                )}
                {draft.id && shouldOfferRevision(draft.status, draft.stale) && (
                  <button
                    type="button"
                    onClick={handleRevision}
                    disabled={busy}
                    className="min-h-11 rounded border border-amber-600 px-4 py-3 text-amber-800 disabled:opacity-50"
                  >
                    Tạo revision
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleExportRecord("pyc", "xlsx")}
                  disabled={busy}
                  className="rounded bg-slate-700 px-4 py-3 text-white disabled:opacity-50"
                >
                  PYC Excel
                </button>
                <button
                  type="button"
                  onClick={() => handleExportRecord("pyc", "pdf")}
                  disabled={busy}
                  className="rounded bg-slate-700 px-4 py-3 text-white disabled:opacity-50"
                >
                  PYC PDF
                </button>
                <button
                  type="button"
                  onClick={() => handleExportRecord("bbnt", "xlsx")}
                  disabled={busy || draft.status !== "confirmed"}
                  title={
                    draft.status !== "confirmed"
                      ? "BBNT phải được người có quyền xác nhận trước khi xuất"
                      : undefined
                  }
                  className="rounded bg-slate-700 px-4 py-3 text-white disabled:opacity-50"
                >
                  BBNT Excel
                </button>
                <button
                  type="button"
                  onClick={() => handleExportRecord("bbnt", "pdf")}
                  disabled={busy || draft.status !== "confirmed"}
                  title={
                    draft.status !== "confirmed"
                      ? "BBNT phải được người có quyền xác nhận trước khi xuất"
                      : undefined
                  }
                  className="rounded bg-slate-700 px-4 py-3 text-white disabled:opacity-50"
                >
                  BBNT PDF
                </button>
                <button
                  type="button"
                  onClick={closeRecordEditor}
                  className="min-h-11 rounded border px-4 py-3"
                >
                  Đóng
                </button>
              </div>

              {draft.status !== "confirmed" && !draft.id && (
                <p className="text-xs text-slate-500">
                  Lưu nháp trước, sau đó người có quyền mới có thể xác nhận.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <NumberingPanel
          projectId={projectId}
          onSaved={() => {
            void refresh();
          }}
        />
        <AcceptanceHistoryPanel
          projectId={projectId}
          onOpenRequest={openRequestById}
          onOpenRecord={openRecordById}
        />
      </div>

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
