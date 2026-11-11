import { useEffect, useState } from "react";
import ConfirmDialog from "../components/ConfirmDialog";
import ParticipantLibrary from "../components/ParticipantLibrary";
import ParticipantsEditor from "../components/ParticipantsEditor";
import RequestForm from "../components/RequestForm";
import TriStateChecklist from "../components/TriStateChecklist";
import {
  AcceptanceApiError,
  createRecord,
  createRecordRevision,
  createRequest,
  exportDownloadUrl,
  exportRecord,
  exportRequest,
  getRequestDailyReport,
  listParticipantProfiles,
  listRecords,
  listRequests,
  previewRecord,
  previewRequest,
  updateRecord,
  updateRequest,
} from "../lib/api";
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
  RecordInput,
  RequestInput,
  ResultState,
  YesNo,
} from "../types";
import { emptyChecklist } from "../types";

type Props = { projectId: string };

type Tab = "requests" | "records";

type RecordDraft = {
  id?: string;
  request_id: string;
  request_number?: string;
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

function draftFor(record: AcceptanceRecord, request?: AcceptanceRequest): RecordDraft {
  return {
    id: record.id,
    request_id: record.request_id,
    request_number: request?.number,
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

function newDraft(request: AcceptanceRequest): RecordDraft {
  return {
    request_id: request.id,
    request_number: request.number,
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

export default function AcceptancePage({ projectId }: Props) {
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
  const [preview, setPreview] = useState<PreviewPayload | null>(null);

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
        const [requestList, recordList, profileList] = await Promise.all([
          listRequests(projectId),
          listRecords(projectId),
          listParticipantProfiles(projectId),
        ]);
        if (!active) return;
        setRequests(requestList);
        setRecords(recordList);
        setProfiles(profileList);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    })();
    setDraft(null);
    setEditingRequest(null);
    setLastExport(null);
    setPreview(null);
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

  async function saveRequest(input: RequestInput) {
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
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
      throw cause;
    } finally {
      setBusy(false);
    }
  }

  function startRecord(request: AcceptanceRequest) {
    const existing = recordFor(request.id);
    setError(null);
    setMessage(null);
    setTab("records");
    if (existing) {
      if (existing.status === "confirmed") {
        setMessage("BBNT đã được xác nhận và chỉ được xem/xuất.");
      }
      setDraft(draftFor(existing, request));
    } else {
      setDraft(newDraft(request));
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
      setDraft(draftFor(saved, request));
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
      setDraft(draftFor(confirmed, request));
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
    setBusy(true);
    setError(null);
    try {
      const revised = await createRecordRevision(projectId, draft.id);
      const { requestList, recordList } = await refresh();
      const request = requestList.find((item) => item.id === revised.request_id);
      setDraft(draftFor(revised, request));
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

  const selectedRequest = editingRequest && editingRequest !== "new" ? editingRequest : null;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Nghiệm thu (PYC / BBNT)</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTab("requests")}
            className={`rounded px-3 py-2 text-sm ${tab === "requests" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Phiếu yêu cầu (PYC)
          </button>
          <button
            type="button"
            onClick={() => setTab("records")}
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
          <a className="text-teal-700 underline" href={exportDownloadUrl(lastExport)}>
            tải {lastExport.kind.toUpperCase()} (.{lastExport.format})
          </a>{" "}
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
                initial={selectedRequest}
                dailyReport={
                  selectedRequest
                    ? reportLinks[selectedRequest.id] ?? null
                    : null
                }
                profiles={profiles}
                submitting={busy}
                onSubmit={saveRequest}
                onCancel={() => setEditingRequest(null)}
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
                      onClick={() => setEditingRequest(request)}
                      className="rounded border px-3 py-2 text-sm"
                    >
                      Sửa
                    </button>
                    <button
                      type="button"
                      onClick={() => startRecord(request)}
                      className="rounded border border-teal-700 px-3 py-2 text-sm text-teal-800"
                    >
                      {record ? "Mở BBNT" : "Tạo BBNT"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handlePreviewRequest(request)}
                      className="rounded border px-3 py-2 text-sm"
                    >
                      Xem trước
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExportRequest(request, "xlsx")}
                      disabled={busy}
                      className="rounded bg-slate-700 px-3 py-2 text-sm text-white disabled:opacity-50"
                    >
                      PYC Excel
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExportRequest(request, "pdf")}
                      disabled={busy}
                      className="rounded bg-slate-700 px-3 py-2 text-sm text-white disabled:opacity-50"
                    >
                      PYC PDF
                    </button>
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

              {reportLinks[draft.request_id] && (
                <div className="rounded bg-teal-50 p-2 text-sm text-teal-900">
                  Báo cáo ngày liên kết:{" "}
                  {reportLinks[draft.request_id]?.report_date} (
                  {reportLinks[draft.request_id]?.status}) —{" "}
                  <a
                    className="underline"
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
                    onChange={(event) => setDraft({ ...draft, record_date: event.target.value })}
                  />
                </label>
                <label className="block text-sm">
                  Bắt đầu
                  <input
                    className="mt-1 w-full rounded border p-3"
                    value={draft.start_time}
                    placeholder="Ví dụ: 15h00"
                    disabled={draft.status === "confirmed"}
                    onChange={(event) => setDraft({ ...draft, start_time: event.target.value })}
                  />
                </label>
                <label className="block text-sm">
                  Kết thúc
                  <input
                    className="mt-1 w-full rounded border p-3"
                    value={draft.end_time}
                    placeholder="Ví dụ: 16h20"
                    disabled={draft.status === "confirmed"}
                    onChange={(event) => setDraft({ ...draft, end_time: event.target.value })}
                  />
                </label>
                <label className="block text-sm">
                  So với thiết kế
                  <select
                    className="mt-1 w-full rounded border p-3"
                    value={draft.design_compliance}
                    disabled={draft.status === "confirmed"}
                    onChange={(event) =>
                      setDraft({ ...draft, design_compliance: event.target.value as YesNo | "" })
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
                      setDraft({
                        ...draft,
                        technical_compliance: event.target.value as YesNo | "",
                      })
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
                  onChange={(event) => setDraft({ ...draft, other_notes: event.target.value })}
                />
              </label>

              <ParticipantsEditor
                items={draft.participants}
                disabled={draft.status === "confirmed"}
                onChange={(participants) => setDraft({ ...draft, participants })}
              />

              <TriStateChecklist
                items={draft.checklist}
                disabled={draft.status === "confirmed"}
                onChange={(checklist) => setDraft({ ...draft, checklist })}
              />

              <label className="block text-sm">
                Ghi chú kết luận (chỉ người xác nhận ghi)
                <textarea
                  className="mt-1 w-full rounded border p-3"
                  rows={2}
                  value={draft.conclusion_note}
                  disabled={draft.status === "confirmed"}
                  onChange={(event) => setDraft({ ...draft, conclusion_note: event.target.value })}
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
                {draft.id && (
                  <button
                    type="button"
                    onClick={handleRevision}
                    disabled={busy}
                    className="rounded border border-amber-600 px-4 py-3 text-amber-800 disabled:opacity-50"
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
                  onClick={() => setDraft(null)}
                  className="rounded border px-4 py-3"
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
