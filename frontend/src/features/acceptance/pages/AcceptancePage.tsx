import { useEffect, useMemo, useRef, useState } from "react";
import AcceptanceHistoryPanel from "../components/AcceptanceHistoryPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import NumberingPanel from "../components/NumberingPanel";
import ParticipantLibrary from "../components/ParticipantLibrary";
import ParticipantsEditor from "../components/ParticipantsEditor";
import RequestForm from "../components/RequestForm";
import TriStateChecklist from "../components/TriStateChecklist";
import MenuButton from "../../../ui/MenuButton";
import {
  AcceptanceApiError,
  createRecord,
  createRecordRevision,
  createRequest,
  createRequestFromComponents,
  deleteRequest,
  downloadExport,
  exportRecord,
  exportRequest,
  fetchRequestPreviewImage,
  getProjectContext,
  getRequestDailyReport,
  listParticipantProfiles,
  listPendingAcceptance,
  listRecords,
  listRequests,
  listWorkItems,
  previewRecord,
  previewRequest,
  updateRecord,
  updateRequest,
} from "../lib/api";
import { latestRequestForPrefill } from "../lib/requestPrefill";
import { projectMetadataDefaults } from "../lib/projectPrefill";
import {
  recordStatusLabel,
  requestStatusLabel,
  resultLabel,
  revisionLabel,
  STATUS_LEGEND,
} from "../lib/statusLabels";
import {
  buildWhatsAppInvite,
  whatsAppInviteUrl,
} from "../lib/whatsappInvite";
import { confirmRecord } from "../lib/api";
import type {
  AcceptanceExport,
  AcceptanceNavigationPayload,
  AcceptanceRecord,
  AcceptanceRequest,
  ChecklistInput,
  LinkedDailyReport,
  ParticipantInput,
  ParticipantProfile,
  PendingAcceptanceResponse,
  PreviewPayload,
  ProjectContext,
  RecordInput,
  RequestInput,
  ResultState,
  WorkItemSummary,
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
  /**
   * App-level navigation payload from the site paste flow.  The app shell owns
   * the type in ``frontend/src/app``; this page reads it through this prop.
   */
  initialState?: AcceptanceNavigationPayload | null;
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

function shortDate(value: string): string {
  const [year, month, day] = value.split("-");
  return year && month && day ? `${day}/${month}/${year}` : value;
}

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

export default function AcceptancePage({
  projectId,
  onDirtyChange,
  initialState,
}: Props) {
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
  const [downloadFailed, setDownloadFailed] = useState(false);
  const [reportLinks, setReportLinks] = useState<
    Record<string, LinkedDailyReport | null>
  >({});
  const [profiles, setProfiles] = useState<ParticipantProfile[]>([]);
  const [workItems, setWorkItems] = useState<WorkItemSummary[]>([]);
  const [projectContext, setProjectContext] = useState<ProjectContext | null>(null);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [requestDirty, setRequestDirty] = useState(false);
  const [recordDirty, setRecordDirty] = useState(false);
  const [pending, setPending] = useState<PendingAcceptanceResponse | null>(null);
  const [pendingSelected, setPendingSelected] = useState<Set<string>>(new Set());
  const [pendingBusy, setPendingBusy] = useState(false);
  const [pendingFilterCleared, setPendingFilterCleared] = useState(false);
  const [pendingTotalAll, setPendingTotalAll] = useState<number | null>(null);
  const hasPendingFilter = Boolean(
    initialState?.stage_definition_id || initialState?.batch_id,
  );
  const pendingFilterActive = hasPendingFilter && !pendingFilterCleared;
  const initialComponentKey = (initialState?.component_ids ?? []).join(",");
  const onDirtyChangeRef = useRef(onDirtyChange);

  useEffect(() => {
    onDirtyChangeRef.current = onDirtyChange;
    onDirtyChange?.(requestDirty || recordDirty);
  }, [onDirtyChange]);

  useEffect(() => {
    onDirtyChangeRef.current?.(requestDirty || recordDirty);
  }, [requestDirty, recordDirty]);

  useEffect(() => {
    if (!previewImageUrl) return;
    return () => URL.revokeObjectURL(previewImageUrl);
  }, [previewImageUrl]);

  function closePreview() {
    setPreview(null);
    setPreviewImageUrl(null);
  }

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

  async function loadPending(options: { all?: boolean } = {}) {
    const useFilter = pendingFilterActive && !options.all;
    const filters = useFilter
      ? {
          batch_id: initialState?.batch_id,
          stage_definition_id: initialState?.stage_definition_id,
        }
      : {};
    const [data, all] = await Promise.all([
      listPendingAcceptance(projectId, filters),
      useFilter ? listPendingAcceptance(projectId) : Promise.resolve(null),
    ]);
    setPending(data);
    setPendingTotalAll(all ? all.total_components : data.total_components);
    return data;
  }

  async function clearPendingFilter() {
    setPendingFilterCleared(true);
    setPendingSelected(new Set());
    try {
      await loadPending({ all: true });
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function togglePending(componentId: string) {
    setPendingSelected((current) => {
      const next = new Set(current);
      if (next.has(componentId)) next.delete(componentId);
      else next.add(componentId);
      return next;
    });
  }

  async function createPendingRequest() {
    if (pendingSelected.size === 0 || pendingBusy) return;
    setPendingBusy(true);
    setError(null);
    try {
      const created = await createRequestFromComponents(projectId, {
        component_ids: [...pendingSelected],
        stage_definition_id: pendingFilterActive
          ? initialState?.stage_definition_id ?? null
          : null,
        event_date: initialState?.event_date ?? null,
      });
      await Promise.all([refresh(), loadPending()]);
      setPendingSelected(new Set());
      setTab("requests");
      setEditingRequest(created);
      setMessage(
        `Đã tạo PYC nháp ${created.number} cho ${pendingSelected.size} cấu kiện. Chưa xác nhận nghiệm thu.`,
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPendingBusy(false);
    }
  }

  useEffect(() => {
    let active = true;
    setPending(null);
    setPendingFilterCleared(false);
    setPendingSelected(new Set(initialState?.component_ids ?? []));
    const filters = hasPendingFilter
      ? {
          batch_id: initialState?.batch_id,
          stage_definition_id: initialState?.stage_definition_id,
        }
      : {};
    Promise.all([
      listPendingAcceptance(projectId, filters),
      hasPendingFilter
        ? listPendingAcceptance(projectId)
        : Promise.resolve(null),
    ])
      .then(([data, all]) => {
        if (!active) return;
        setPending(data);
        setPendingTotalAll(all ? all.total_components : data.total_components);
        const pendingIds = new Set(
          data.groups.flatMap((group) =>
            group.components.map((component) => component.component_id),
          ),
        );
        const requested = initialState?.component_ids ?? [];
        if (requested.length) {
          setPendingSelected(
            new Set(requested.filter((componentId) => pendingIds.has(componentId))),
          );
        }
      })
      .catch((cause) => {
        if (active) setError(errorMessage(cause));
      });
    return () => {
      active = false;
    };
    // The navigation payload is read once per project/initial navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, initialState?.batch_id, initialState?.stage_definition_id, initialComponentKey]);

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
    closePreview();
    setProjectContext(null);
    setRequestDirty(false);
    setRecordDirty(false);
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    setWorkItems([]);
    // Keep this separate from the main Promise.all: a failing work-item
    // catalog must not block PYC/BBNT loading.
    listWorkItems(projectId)
      .then((items) => {
        if (active) setWorkItems(items);
      })
      .catch(() => {
        if (active) setWorkItems([]);
      });
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

  const recordsByRequest = useMemo(() => {
    const map = new Map<string, AcceptanceRecord>();
    for (const record of records) {
      if (!map.has(record.request_id)) map.set(record.request_id, record);
    }
    return map;
  }, [records]);

  function recordFor(requestId: string): AcceptanceRecord | undefined {
    return recordsByRequest.get(requestId);
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

  async function handleExportRequest(request: AcceptanceRequest, format: "xlsx" | "pdf") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const exported = await exportRequest(projectId, request.id, format);
      setLastExport(exported);
      try {
        const filename = await downloadExport(exported);
        setDownloadFailed(false);
        setMessage(
          `Đã xuất và tải ${filename}. Chỉ các ô đã kiểm tra được ghi.`,
        );
      } catch (downloadError) {
        setDownloadFailed(true);
        setError(
          `${errorMessage(downloadError)} File ${format.toUpperCase()} PYC ${request.number} đã tạo nhưng chưa tải được; bấm "Tải lại" bên dưới.`,
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
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

  async function handlePreviewRequest(request: AcceptanceRequest) {
    setError(null);
    setPreviewBusy(true);
    closePreview();
    try {
      const data = await previewRequest(projectId, request.id);
      setPreview(data);
      try {
        const imageUrl = await fetchRequestPreviewImage(projectId, request.id);
        setPreviewImageUrl(imageUrl);
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : "Không tạo được ảnh xem trước PYC.",
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function handlePreviewRecord() {
    if (!draft?.id) {
      setError("Cần lưu BBNT trước khi xem trước.");
      return;
    }
    setError(null);
    closePreview();
    try {
      setPreview(await previewRecord(projectId, draft.id));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  async function handleDeleteRequest(request: AcceptanceRequest) {
    if (busy) return;
    const record = recordFor(request.id);
    const warning = record
      ? `PYC ${request.number} đã có BBNT (${recordStatusLabel(record.status)}). Xoá PYC sẽ xoá luôn BBNT liên quan và lịch sử xuất file. Không thể hoàn tác. Tiếp tục?`
      : request.status === "submitted"
        ? `PYC ${request.number} đã gửi. Xoá phiếu này và lịch sử xuất file? Không thể hoàn tác.`
        : `Xoá PYC ${request.number}? Không thể hoàn tác.`;
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

  async function handleExportRecord(kind: "pyc" | "bbnt", format: "xlsx" | "pdf") {
    if (!draft?.id) {
      setError("Cần lưu BBNT trước khi xuất.");
      return;
    }
    const recordId = draft.id;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const exported = await exportRecord(projectId, recordId, kind, format);
      setLastExport(exported);
      try {
        const filename = await downloadExport(exported);
        setDownloadFailed(false);
        setMessage(
          kind === "bbnt"
            ? `Đã xuất và tải ${filename}. Bản xuất dùng dữ liệu đã được con người xác nhận.`
            : `Đã xuất và tải ${filename}. Sheet BBNT được để trống an toàn.`,
        );
      } catch (downloadError) {
        setDownloadFailed(true);
        setError(
          `${errorMessage(downloadError)} File ${format.toUpperCase()} ${kind.toUpperCase()} đã tạo nhưng chưa tải được; bấm "Tải lại" bên dưới.`,
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadExport(exported: AcceptanceExport) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const filename = await downloadExport(exported);
      setDownloadFailed(false);
      setMessage(`Đã tải ${filename}.`);
    } catch (cause) {
      setDownloadFailed(true);
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const selectedRequest = editingRequest && editingRequest !== "new" ? editingRequest : null;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[#405e9b]">Điều hành</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Nghiệm thu (PYC / BBNT)</h1>
          <p className="mt-1 text-sm text-slate-600">Lập phiếu yêu cầu, biên bản và xuất hồ sơ nghiệm thu.</p>
        </div>
        <div role="group" aria-label="Khu vực nghiệm thu" className="flex gap-2">
          <button
            type="button"
            aria-pressed={tab === "requests"}
            onClick={() => switchTab("requests")}
            className={`min-h-11 rounded-xl px-3 py-2 text-sm font-medium ${tab === "requests" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Phiếu yêu cầu (PYC)
          </button>
          <button
            type="button"
            aria-pressed={tab === "records"}
            onClick={() => switchTab("records")}
            className={`min-h-11 rounded-xl px-3 py-2 text-sm font-medium ${tab === "records" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Biên bản nghiệm thu (BBNT)
          </button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2" aria-label="Chú giải trạng thái">
        <span className="text-sm font-medium text-slate-600">Trạng thái:</span>
        {STATUS_LEGEND.map((item) => (
          <span
            key={item.label}
            className={`rounded-full border px-2 py-1 text-sm ${item.className}`}
          >
            {item.label}
          </span>
        ))}
      </div>

      {pending && (pending.total_components > 0 || pendingFilterActive) && (
        <section
          aria-label="Chờ nghiệm thu"
          className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 shadow-sm sm:p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-amber-950">
              Chờ nghiệm thu (
              {pendingFilterActive && pendingTotalAll !== null
                ? `${pending.total_components} / ${pendingTotalAll}`
                : pending.total_components}
              )
            </h2>
            <span className="text-sm text-amber-900">
              Hoàn thành thi công, chưa có BBNT xác nhận
            </span>
          </div>
          {pendingFilterActive && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-amber-300 bg-white px-3 py-1 text-sm text-amber-950">
                Đang lọc:{" "}
                <strong className="[overflow-wrap:anywhere]">
                  {pending.stage_name ?? "đợt thi công đã chọn"}
                </strong>
              </span>
              <button
                type="button"
                onClick={() => void clearPendingFilter()}
                className="min-h-11 text-sm font-medium text-teal-800 underline"
              >
                Xem tất cả
              </button>
            </div>
          )}
          <p className="mt-1 text-sm leading-6 text-amber-900">
            Tiến độ thi công không phải nghiệm thu. Chọn cấu kiện để lập phiếu
            yêu cầu; BBNT chỉ được xác nhận bởi người có quyền.
          </p>
          <div className="mt-3 space-y-3">
            {pending.groups.map((group) => (
              <div
                key={`${group.stage_name}-${group.zone}-${group.segment}`}
                className="rounded-lg border border-amber-200 bg-white p-3"
              >
                <h3 className="text-sm font-semibold text-slate-900 [overflow-wrap:anywhere]">
                  {group.stage_name}
                </h3>
                <p className="mt-0.5 text-sm text-slate-600">
                  {group.zone} · Phân đoạn {group.segment} ·{" "}
                  {group.event_dates.map(shortDate).join(", ")}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {group.components.map((component) => {
                    const selected = pendingSelected.has(component.component_id);
                    return (
                      <label
                        key={component.component_id}
                        className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                          selected
                            ? "border-teal-700 bg-teal-50 text-teal-900"
                            : "border-slate-300 bg-white text-slate-800"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="h-5 w-5 accent-teal-700"
                          checked={selected}
                          onChange={() => togglePending(component.component_id)}
                        />
                        <span className="font-medium">{component.code}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => void createPendingRequest()}
            disabled={pendingSelected.size === 0 || pendingBusy}
            className="mt-3 min-h-11 w-full rounded bg-teal-700 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50 sm:w-auto"
          >
            {pendingBusy
              ? "Đang tạo PYC nháp..."
              : `Tạo PYC nháp cho ${pendingSelected.size} cấu kiện`}
          </button>
        </section>
      )}

      {error && !editingRequest && !draft && (
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
            {downloadFailed ? "Tải lại" : "Tải xuống lại"}{" "}
            {lastExport.kind.toUpperCase()} (.{lastExport.format})
          </button>{" "}
          <span className="text-slate-500">sha256 {lastExport.sha256.slice(0, 12)}…</span>
        </div>
      )}

      {preview && (
        <section className="rounded-xl bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Xem trước {preview.kind.toUpperCase()}</h2>
            <button
              type="button"
              className="inline-flex min-h-11 items-center text-sm underline"
              onClick={closePreview}
            >
              Đóng
            </button>
          </div>
          {preview.warnings.map((warning) => (
            <p key={warning} className="mt-2 rounded bg-amber-50 p-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}
          {preview.kind === "pyc" ? (
            previewImageUrl ? (
              <div className="mt-2 space-y-2">
                <img
                  src={previewImageUrl}
                  alt="Ảnh xem trước phiếu yêu cầu nghiệm thu"
                  className="w-full rounded border border-slate-200 bg-white shadow-sm"
                />
                <p className="text-sm text-slate-500">
                  Ảnh được tạo từ mẫu Excel đã điền dữ liệu; bản chính thức chỉ
                  được tạo khi bấm xuất file.
                </p>
              </div>
            ) : (
              <p className="mt-2 rounded bg-slate-50 p-3 text-sm text-slate-600">
                {previewBusy
                  ? "Đang tạo ảnh xem trước PYC…"
                  : "Chưa tạo được ảnh xem trước. Xem thông báo lỗi phía trên."}
              </p>
            )
          ) : (
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-sm">
              {JSON.stringify(preview.cells, null, 2)}
            </pre>
          )}
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
                onSubmit={saveRequest}
                onDirtyChange={setRequestDirty}
                onCancel={closeRequestEditor}
              />
            </div>
          ) : (
            <div className="space-y-1">
              <button
                type="button"
                onClick={() => setEditingRequest("new")}
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
                          {request.location || request.subject || request.project_name || "Chưa có nội dung"}
                        </p>
                        {request.daily_report_id && (
                          <p className="text-sm text-teal-800">
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
                    <MenuButton
                      label="Thao tác"
                      triggerClassName="min-h-11 cursor-pointer rounded border px-4 py-2 text-sm"
                      panelClassName="right-0 w-48 rounded border bg-white p-1 shadow-lg"
                    >
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
                        disabled={busy || previewBusy}
                        className="block min-h-11 w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                      >
                        {previewBusy ? "Đang tạo ảnh xem trước…" : "Xem trước"}
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
                      <button
                        type="button"
                        onClick={() => void handleCopyInvite(request)}
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
                        onClick={() => void handleDeleteRequest(request)}
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
      )}

      {tab === "records" && (
        <div className="space-y-4">
          {message && !draft && (
            <p role="status" className="rounded bg-emerald-50 p-3 text-sm text-emerald-900">
              {message}
            </p>
          )}
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
                        PYC {request.number} {record ? `— BBNT ${recordStatusLabel(record.status)}` : "— chưa có BBNT"}
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
                  — {revisionLabel(draft.revision)}
                </h2>
                <span className="text-sm rounded bg-slate-100 px-2 py-1 text-slate-700">
                  {draft.status === "confirmed"
                    ? `Đã xác nhận: ${resultLabel(draft.result) || "—"}`
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
              <p className="text-sm text-slate-500">
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
                      onClick={saveRecord}
                      disabled={busy}
                      className="min-h-11 rounded bg-teal-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
                    >
                      {busy ? "Đang lưu..." : "Lưu BBNT nháp"}
                    </button>
                  )}
                  {draft.status !== "confirmed" && draft.id && (
                    <button
                      type="button"
                      onClick={() => setConfirming(true)}
                      disabled={busy}
                      className="min-h-11 rounded bg-emerald-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
                    >
                      Xác nhận BBNT
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={closeRecordEditor}
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
                          onClick={handlePreviewRecord}
                          disabled={busy}
                          className="min-h-11 rounded border px-4 py-3 text-sm disabled:opacity-50"
                        >
                          Xem trước
                        </button>
                      )}
                      {draft.id && shouldOfferRevision(draft.status, draft.stale) && (
                        <button
                          type="button"
                          onClick={handleRevision}
                          disabled={busy}
                          className="min-h-11 rounded border border-amber-600 px-4 py-3 text-sm text-amber-800 disabled:opacity-50"
                        >
                          Tạo bản sửa
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleExportRecord("pyc", "xlsx")}
                        disabled={busy}
                        className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
                      >
                        PYC Excel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExportRecord("pyc", "pdf")}
                        disabled={busy}
                        className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
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
                        className="min-h-11 rounded bg-slate-700 px-4 py-3 text-sm text-white disabled:opacity-50"
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
          )}
        </div>
      )}

      <details className="rounded-xl bg-white p-4 shadow-sm">
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-slate-800">
          Cài đặt nghiệm thu
          <span className="ml-auto text-sm font-normal text-slate-500">
            Danh bạ &amp; cấu hình số
          </span>
        </summary>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <ParticipantLibrary projectId={projectId} onChanged={setProfiles} />
          <NumberingPanel
            projectId={projectId}
            onSaved={() => {
              void refresh();
            }}
          />
        </div>
      </details>

      <AcceptanceHistoryPanel
        projectId={projectId}
        onOpenRequest={openRequestById}
        onOpenRecord={openRecordById}
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

