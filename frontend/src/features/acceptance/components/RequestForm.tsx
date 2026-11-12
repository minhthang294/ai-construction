import { useEffect, useState } from "react";
import { getDailyReportByDate } from "../lib/api";
import { shouldMarkSaved } from "../lib/formGuard";
import {
  mergeProjectMetadata,
  projectMetadataDefaults,
} from "../lib/projectPrefill";
import type {
  AcceptanceRequest,
  FieldKind,
  LinkedDailyReport,
  ParticipantProfile,
  ProjectContext,
  RequestInput,
  Urgency,
} from "../types";

type Props = {
  projectId: string;
  project?: ProjectContext | null;
  initial?: AcceptanceRequest | null;
  dailyReport?: LinkedDailyReport | null;
  profiles?: ParticipantProfile[];
  onSubmit: (input: RequestInput) => Promise<boolean | void> | boolean | void;
  onCancel?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  submitting?: boolean;
};

type FormState = {
  number: string;
  daily_report_id: string;
  requested_by_profile_id: string;
  supervisor_profile_id: string;
  investor_profile_id: string;
  project_name: string;
  client: string;
  project_location: string;
  location: string;
  request_date: string;
  inspection_time: string;
  content: string;
  subject: string;
  field: FieldKind | "";
  urgency: Urgency | "";
  requested_by_name: string;
  supervisor_name: string;
  investor_name: string;
  contractor_org: string;
  supervisor_org: string;
  investor_org: string;
  notes: string;
};

const BLANK: FormState = {
  number: "",
  daily_report_id: "",
  requested_by_profile_id: "",
  supervisor_profile_id: "",
  investor_profile_id: "",
  project_name: "",
  client: "",
  project_location: "",
  location: "",
  request_date: "",
  inspection_time: "",
  content: "",
  subject: "",
  field: "",
  urgency: "normal",
  requested_by_name: "",
  supervisor_name: "",
  investor_name: "",
  contractor_org: "",
  supervisor_org: "",
  investor_org: "",
  notes: "",
};

function toForm(
  request?: AcceptanceRequest | null,
  project?: ProjectContext | null,
): FormState {
  if (!request) {
    return { ...BLANK, ...projectMetadataDefaults(project) };
  }
  return mergeProjectMetadata(
    {
      number: request.number ?? "",
      daily_report_id: request.daily_report_id ?? "",
      requested_by_profile_id: request.requested_by_profile_id ?? "",
      supervisor_profile_id: request.supervisor_profile_id ?? "",
      investor_profile_id: request.investor_profile_id ?? "",
      project_name: request.project_name ?? "",
      client: request.client ?? "",
      project_location: request.project_location ?? "",
      location: request.location ?? "",
      request_date: request.request_date ?? "",
      inspection_time: request.inspection_time ?? "",
      content: request.content ?? "",
      subject: request.subject ?? "",
      field: request.field ?? "",
      urgency: request.urgency ?? "normal",
      requested_by_name: request.requested_by_name ?? "",
      supervisor_name: request.supervisor_name ?? "",
      investor_name: request.investor_name ?? "",
      contractor_org: request.contractor_org ?? "",
      supervisor_org: request.supervisor_org ?? "",
      investor_org: request.investor_org ?? request.client ?? "",
      notes: request.notes ?? "",
    },
    project,
  );
}

function nullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export default function RequestForm({
  projectId,
  project,
  initial,
  dailyReport,
  profiles = [],
  onSubmit,
  onCancel,
  onDirtyChange,
  submitting = false,
}: Props) {
  const [form, setForm] = useState<FormState>(() => toForm(initial, project));
  const [error, setError] = useState<string | null>(null);
  const [dailyReportDate, setDailyReportDate] = useState(dailyReport?.report_date ?? "");
  const [linkedReport, setLinkedReport] = useState<LinkedDailyReport | null>(
    dailyReport ?? null,
  );
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  useEffect(() => {
    setForm(toForm(initial, project));
    setLinkedReport(dailyReport ?? null);
    setDailyReportDate(dailyReport?.report_date ?? "");
    setReportMessage(null);
    setError(null);
    onDirtyChange?.(false);
  }, [initial?.id, project?.id]);

  useEffect(() => {
    if (!dailyReport) return;
    setLinkedReport(dailyReport);
    setDailyReportDate(dailyReport.report_date);
    setForm((previous) => ({ ...previous, daily_report_id: dailyReport.id }));
  }, [dailyReport?.id]);

  async function lookupDailyReport(value: string) {
    setDailyReportDate(value);
    setReportMessage(null);
    if (!value) {
      setLinkedReport(null);
      setForm((previous) => ({ ...previous, daily_report_id: "" }));
      return;
    }
    setLookupBusy(true);
    try {
      const report = await getDailyReportByDate(projectId, value);
      if (report) {
        setLinkedReport(report);
        setForm((previous) => ({ ...previous, daily_report_id: report.id }));
        setReportMessage(`Đã liên kết báo cáo ngày ${report.report_date}.`);
      } else {
        setLinkedReport(null);
        setForm((previous) => ({ ...previous, daily_report_id: "" }));
        setReportMessage("Không có báo cáo ngày cho ngày này.");
      }
    } catch (cause) {
      setReportMessage(
        cause instanceof Error ? cause.message : "Không đọc được báo cáo ngày.",
      );
    } finally {
      setLookupBusy(false);
    }
  }

  function clearDailyReport() {
    setLinkedReport(null);
    setDailyReportDate("");
    setReportMessage(null);
    setForm((previous) => ({ ...previous, daily_report_id: "" }));
    onDirtyChange?.(true);
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const payload: RequestInput = {
      number: form.number.trim() || null,
      daily_report_id: nullable(form.daily_report_id),
      requested_by_profile_id: nullable(form.requested_by_profile_id),
      supervisor_profile_id: nullable(form.supervisor_profile_id),
      investor_profile_id: nullable(form.investor_profile_id),
      status: initial?.status === "submitted" ? "submitted" : "draft",
      project_name: nullable(form.project_name),
      client: nullable(form.client),
      project_location: nullable(form.project_location),
      location: nullable(form.location),
      request_date: nullable(form.request_date),
      inspection_time: nullable(form.inspection_time),
      content: nullable(form.content),
      subject: nullable(form.subject),
      field: form.field || null,
      urgency: form.urgency || null,
      requested_by_name: nullable(form.requested_by_name),
      supervisor_name: nullable(form.supervisor_name),
      investor_name: nullable(form.investor_name),
      contractor_org: nullable(form.contractor_org),
      supervisor_org: nullable(form.supervisor_org),
      investor_org: nullable(form.investor_org),
      notes: nullable(form.notes),
    };
    try {
      const result = await onSubmit(payload);
      if (shouldMarkSaved(result)) onDirtyChange?.(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không lưu được PYC.");
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      onChange={() => onDirtyChange?.(true)}
      className="space-y-3"
      aria-label="Phiếu yêu cầu nghiệm thu"
    >
      <h2 className="text-lg font-semibold">
        {initial ? `Sửa PYC ${initial.number}` : "Tạo PYC nháp"}
      </h2>
      <p className="rounded bg-slate-50 p-2 text-xs text-slate-600">
        Tên công trình, Chủ đầu tư và Địa điểm được điền sẵn từ Thiết lập công
        trình; chỉ sửa khi PYC này cần giá trị khác.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Số PYC (để trống để tự cấp)
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.number}
            onChange={(event) => set("number", event.target.value)}
            placeholder="Tự cấp theo cấu hình numbering"
          />
        </label>
        <label className="block text-sm">
          Ngày yêu cầu
          <input
            type="date"
            className="mt-1 w-full rounded border p-3"
            value={form.request_date}
            onChange={(event) => set("request_date", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Tên công trình
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.project_name}
            onChange={(event) => set("project_name", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Chủ đầu tư
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.client}
            onChange={(event) => set("client", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Địa điểm công trình
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.project_location}
            onChange={(event) => set("project_location", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Vị trí / phân đoạn nghiệm thu
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.location}
            onChange={(event) => set("location", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Thời gian nghiệm thu
          <input
            className="mt-1 w-full rounded border p-3"
            placeholder="Ví dụ: 15h00"
            value={form.inspection_time}
            onChange={(event) => set("inspection_time", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Lĩnh vực
          <select
            className="mt-1 w-full rounded border p-3"
            value={form.field}
            onChange={(event) => set("field", event.target.value as FieldKind | "")}
          >
            <option value="">Chưa chọn</option>
            <option value="construction">Xây dựng</option>
            <option value="electric">Điện</option>
            <option value="mechanical">Cơ</option>
          </select>
        </label>
        <label className="block text-sm">
          Mức độ yêu cầu
          <select
            className="mt-1 w-full rounded border p-3"
            value={form.urgency}
            onChange={(event) => set("urgency", event.target.value as Urgency | "")}
          >
            <option value="">Chưa chọn</option>
            <option value="normal">Bình thường</option>
            <option value="urgent">Gấp</option>
            <option value="very_urgent">Rất gấp</option>
          </select>
        </label>
      </div>

      <fieldset className="rounded border p-3">
        <legend className="px-1 text-sm font-semibold">Báo cáo ngày liên kết (chỉ đọc)</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block text-sm">
            Ngày báo cáo
            <input
              type="date"
              className="mt-1 w-full rounded border p-3"
              value={dailyReportDate}
              disabled={lookupBusy}
              onChange={(event) => void lookupDailyReport(event.target.value)}
            />
          </label>
          <div className="text-sm">
            {linkedReport ? (
              <div className="rounded bg-emerald-50 p-2 text-emerald-900">
                <p className="font-medium">
                  Báo cáo {linkedReport.report_date} ({linkedReport.status})
                </p>
                {linkedReport.notes && <p className="mt-1">{linkedReport.notes}</p>}
                <div className="mt-2 flex flex-wrap gap-3">
                  <a
                    className="inline-flex min-h-11 items-center text-teal-800 underline"
                    href={`/api/v1/projects/${projectId}/daily-reports/${linkedReport.report_date}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Xem dữ liệu báo cáo
                  </a>
                  <button
                    type="button"
                    className="inline-flex min-h-11 items-center text-rose-700 underline"
                    onClick={clearDailyReport}
                  >
                    Bỏ liên kết
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-slate-500">Chưa liên kết báo cáo ngày.</p>
            )}
            {reportMessage && <p className="mt-1 text-slate-600">{reportMessage}</p>}
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Liên kết chỉ để đọc và đối chiếu; không tự động xác nhận nghiệm thu.
        </p>
      </fieldset>

      <label className="block text-sm">
        Nội dung nghiệm thu
        <textarea
          className="mt-1 w-full rounded border p-3"
          rows={3}
          value={form.content}
          onChange={(event) => set("content", event.target.value)}
        />
      </label>
      <label className="block text-sm">
        Đối tượng nghiệm thu
        <textarea
          className="mt-1 w-full rounded border p-3"
          rows={2}
          value={form.subject}
          onChange={(event) => set("subject", event.target.value)}
        />
      </label>

      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="text-sm font-semibold mb-1">Người ký PYC</legend>
        <label className="block text-sm">
          Nhà thầu yêu cầu — chọn từ danh bạ
          <select
            className="mt-1 w-full rounded border p-3"
            value={form.requested_by_profile_id}
            onChange={(event) => {
              const profile = profiles.find((item) => item.id === event.target.value);
              setForm((previous) => ({
                ...previous,
                requested_by_profile_id: event.target.value,
                requested_by_name: profile?.full_name ?? previous.requested_by_name,
                contractor_org: profile?.organization ?? previous.contractor_org,
              }));
            }}
          >
            <option value="">Không chọn / nhập tay</option>
            {profiles
              .filter((profile) => profile.active)
              .map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.full_name} — {profile.organization || profile.role}
                </option>
              ))}
          </select>
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.requested_by_name}
            placeholder="Họ tên snapshot"
            onChange={(event) => set("requested_by_name", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Tư vấn giám sát — chọn từ danh bạ
          <select
            className="mt-1 w-full rounded border p-3"
            value={form.supervisor_profile_id}
            onChange={(event) => {
              const profile = profiles.find((item) => item.id === event.target.value);
              setForm((previous) => ({
                ...previous,
                supervisor_profile_id: event.target.value,
                supervisor_name: profile?.full_name ?? previous.supervisor_name,
                supervisor_org: profile?.organization ?? previous.supervisor_org,
              }));
            }}
          >
            <option value="">Không chọn / nhập tay</option>
            {profiles
              .filter((profile) => profile.active)
              .map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.full_name} — {profile.organization || profile.role}
                </option>
              ))}
          </select>
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.supervisor_name}
            placeholder="Họ tên snapshot"
            onChange={(event) => set("supervisor_name", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Chủ đầu tư — chọn từ danh bạ
          <select
            className="mt-1 w-full rounded border p-3"
            value={form.investor_profile_id}
            onChange={(event) => {
              const profile = profiles.find((item) => item.id === event.target.value);
              setForm((previous) => ({
                ...previous,
                investor_profile_id: event.target.value,
                investor_name: profile?.full_name ?? previous.investor_name,
                investor_org: profile?.organization ?? previous.investor_org,
              }));
            }}
          >
            <option value="">Không chọn / nhập tay</option>
            {profiles
              .filter((profile) => profile.active)
              .map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.full_name} — {profile.organization || profile.role}
                </option>
              ))}
          </select>
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.investor_name}
            placeholder="Họ tên snapshot"
            onChange={(event) => set("investor_name", event.target.value)}
          />
        </label>
      </fieldset>

      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="text-sm font-semibold mb-1">Đơn vị</legend>
        <label className="block text-sm">
          Nhà thầu
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.contractor_org}
            onChange={(event) => set("contractor_org", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Tư vấn giám sát
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.supervisor_org}
            onChange={(event) => set("supervisor_org", event.target.value)}
          />
        </label>
        <label className="block text-sm">
          Chủ đầu tư
          <input
            className="mt-1 w-full rounded border p-3"
            value={form.investor_org}
            onChange={(event) => set("investor_org", event.target.value)}
          />
        </label>
      </fieldset>

      <label className="block text-sm">
        Ghi chú
        <textarea
          className="mt-1 w-full rounded border p-3"
          rows={2}
          value={form.notes}
          onChange={(event) => set("notes", event.target.value)}
        />
      </label>

      {error && (
        <p role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-teal-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
        >
          {submitting ? "Đang lưu..." : initial ? "Lưu thay đổi" : "Tạo PYC nháp"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="rounded border px-4 py-3 disabled:opacity-50"
          >
            Hủy
          </button>
        )}
      </div>
    </form>
  );
}
