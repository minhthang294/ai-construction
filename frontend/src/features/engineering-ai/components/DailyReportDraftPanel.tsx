import { useState } from "react";
import { draftDailyReport } from "../lib/api";
import {
  BUTTON_PRIMARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  HELP_TEXT,
  LABEL,
  META_TEXT,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { AlertIcon, SpinnerIcon } from "./icons";
import type { DailyReportDraftResponse } from "../types";

type Props = { projectId: string };
type Mode = "id" | "date" | "json";

const MODES: Array<{ value: Mode; label: string }> = [
  { value: "id", label: "Theo report_id" },
  { value: "date", label: "Theo ngày" },
  { value: "json", label: "Dán JSON" },
];

export default function DailyReportDraftPanel({ projectId }: Props) {
  const [mode, setMode] = useState<Mode>("id");
  const [reportId, setReportId] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [jsonText, setJsonText] = useState("");
  const [result, setResult] = useState<DailyReportDraftResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      let payload: Parameters<typeof draftDailyReport>[1];
      if (mode === "id") {
        if (!reportId.trim()) throw new Error("Nhập report_id của báo cáo ngày.");
        payload = { report_id: reportId.trim() };
      } else if (mode === "date") {
        if (!reportDate) throw new Error("Chọn ngày báo cáo.");
        payload = { report_date: reportDate };
      } else {
        if (!jsonText.trim()) throw new Error("Dán JSON báo cáo ngày đã có.");
        let parsed: unknown;
        try {
          parsed = JSON.parse(jsonText);
        } catch {
          throw new Error("JSON không hợp lệ.");
        }
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("JSON phải là object báo cáo ngày.");
        }
        const source =
          "report" in (parsed as Record<string, unknown>)
            ? (parsed as Record<string, unknown>).report
            : parsed;
        payload = { report: source as Record<string, unknown> };
      }
      setResult(await draftDailyReport(projectId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được bản nháp.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div className="max-w-3xl">
        <h2 className={SECTION_TITLE}>Bản nháp báo cáo ngày từ dữ liệu đã ghi</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          Chỉ sao chép nhân lực, công việc và kế hoạch đã có trong báo cáo nguồn. Không
          tự tạo số lượng/khối lượng; trường thiếu được liệt kê để bổ sung.
        </p>
      </div>

      <div className="max-w-3xl space-y-4">
          <div role="group" aria-label="Cách nhập báo cáo" className="flex flex-wrap gap-2">
          {MODES.map((item) => {
            const active = mode === item.value;
            return (
              <button
                key={item.value}
                type="button"
                aria-pressed={active}
                className={cx(
                  "inline-flex min-h-11 items-center justify-center rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b] focus-visible:ring-offset-2",
                  active
                    ? "bg-[#405e9b] text-white shadow-sm"
                    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
                )}
                onClick={() => {
                  setMode(item.value);
                  setResult(null);
                  setError(null);
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        {mode === "id" && (
          <label className={LABEL} htmlFor="eai-report-id">
            report_id
            <input
              id="eai-report-id"
              className={FIELD}
              value={reportId}
              onChange={(event) => setReportId(event.target.value)}
              placeholder="ID báo cáo ngày đã có"
            />
            <span className={HELP_TEXT}>
              Dùng mã báo cáo đã lưu trong module Báo cáo ngày.
            </span>
          </label>
        )}
        {mode === "date" && (
          <label className={LABEL} htmlFor="eai-report-date">
            Ngày báo cáo
            <input
              id="eai-report-date"
              type="date"
              className={FIELD}
              value={reportDate}
              onChange={(event) => setReportDate(event.target.value)}
            />
          </label>
        )}
        {mode === "json" && (
          <label className={LABEL} htmlFor="eai-report-json">
            JSON DailyReport đã có
            <textarea
              id="eai-report-json"
              className={cx(FIELD, "min-h-48 resize-y font-mono")}
              value={jsonText}
              onChange={(event) => setJsonText(event.target.value)}
              placeholder={'{"report_date":"YYYY-MM-DD","status":"draft","manpower":[],"work_logs":[],"next_day_plans":[]}'}
            />
            <span className={HELP_TEXT}>
              Dán nguyên object báo cáo ngày hoặc object có khóa <code>report</code>.
            </span>
          </label>
        )}

        <button
          type="button"
          className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
          onClick={() => void generate()}
          disabled={busy}
        >
          {busy && <SpinnerIcon className="h-4 w-4" />}
          {busy ? "Đang tạo..." : "Tạo bản nháp"}
        </button>

        {error && (
          <div role="alert" className={PANEL_ALERT}>
            {error}
          </div>
        )}

        {result && (
          <div aria-live="polite" className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-800">
              <p>
                Nguồn: {result.source === "linked" ? "báo cáo liên kết" : "dữ liệu dán"} ·
                trạng thái {result.source_status}
                {result.source_report_id && ` · ${result.source_report_id}`}
              </p>
              <p className="mt-1 font-medium">
                Không tạo khối lượng mới: {result.no_invented_quantities ? "có" : "không"}
              </p>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800">Nội dung sao chép</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-800">
                {result.draft.summary_lines.map((line, index) => (
                  <li key={`${index}-${line}`}>{line}</li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                <AlertIcon className="h-4 w-4 shrink-0" />
                Trường còn thiếu ({result.missing_fields.length})
              </h3>
              {result.missing_fields.length === 0 ? (
                <p className={cx(META_TEXT, "mt-1")}>
                  Không phát hiện trường bắt buộc bị thiếu.
                </p>
              ) : (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-900">
                  {result.missing_fields.map((field, index) => (
                    <li key={`${index}-${field.section}-${field.field}`}>
                      {field.section}
                      {field.index != null ? `[${field.index}]` : ""}.{field.field}: {field.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
              <p>{result.disclaimer}</p>
              {result.warnings.map((warning, index) => (
                <p key={`${index}-${warning}`} className="mt-1">
                  {warning}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
