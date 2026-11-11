import { useState } from "react";
import { draftDailyReport } from "../lib/api";
import type { DailyReportDraftResponse } from "../types";

type Props = { projectId: string };
type Mode = "id" | "date" | "json";

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
    <section className="space-y-3 rounded border border-gray-200 bg-white p-3 shadow-sm">
      <div>
        <h2 className="text-sm font-semibold">Bản nháp báo cáo ngày từ dữ liệu đã ghi</h2>
        <p className="text-xs text-gray-600">
          Chỉ sao chép nhân lực, công việc và kế hoạch đã có trong báo cáo nguồn. Không
          tự tạo số lượng/khối lượng; trường thiếu được liệt kê để bổ sung.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["id", "Theo report_id"],
            ["date", "Theo ngày"],
            ["json", "Dán JSON"],
          ] as Array<[Mode, string]>
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`rounded px-2 py-1 text-xs ${
              mode === value ? "bg-blue-600 text-white" : "border border-gray-300"
            }`}
            onClick={() => {
              setMode(value);
              setResult(null);
              setError(null);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "id" && (
        <label className="block text-xs font-medium text-gray-700">
          report_id
          <input
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            value={reportId}
            onChange={(event) => setReportId(event.target.value)}
            placeholder="ID báo cáo ngày đã có"
          />
        </label>
      )}
      {mode === "date" && (
        <label className="block text-xs font-medium text-gray-700">
          Ngày báo cáo
          <input
            type="date"
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            value={reportDate}
            onChange={(event) => setReportDate(event.target.value)}
          />
        </label>
      )}
      {mode === "json" && (
        <label className="block text-xs font-medium text-gray-700">
          JSON DailyReport đã có
          <textarea
            className="mt-1 h-48 w-full rounded border border-gray-300 p-2 font-mono text-xs"
            value={jsonText}
            onChange={(event) => setJsonText(event.target.value)}
            placeholder={'{"report_date":"YYYY-MM-DD","status":"draft","manpower":[],"work_logs":[],"next_day_plans":[]}'}
          />
        </label>
      )}

      <button
        type="button"
        className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        onClick={() => void generate()}
        disabled={busy}
      >
        {busy ? "Đang tạo..." : "Tạo bản nháp"}
      </button>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {result && (
        <div className="space-y-3">
          <div className="rounded bg-gray-50 p-2 text-xs text-gray-800">
            <p>
              Nguồn: {result.source === "linked" ? "báo cáo liên kết" : "dữ liệu dán"} ·
              trạng thái {result.source_status}
              {result.source_report_id && ` · ${result.source_report_id}`}
            </p>
            <p className="mt-1 font-medium">Không tạo khối lượng mới: {result.no_invented_quantities ? "có" : "không"}</p>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-gray-700">Nội dung sao chép</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-800">
              {result.draft.summary_lines.map((line, index) => (
                <li key={`${index}-${line}`}>{line}</li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-amber-900">
              Trường còn thiếu ({result.missing_fields.length})
            </h3>
            {result.missing_fields.length === 0 ? (
              <p className="text-xs text-gray-600">Không phát hiện trường bắt buộc bị thiếu.</p>
            ) : (
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-amber-900">
                {result.missing_fields.map((field, index) => (
                  <li key={`${index}-${field.section}-${field.field}`}>
                    {field.section}
                    {field.index != null ? `[${field.index}]` : ""}.{field.field}: {field.message}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded bg-amber-50 p-2 text-xs text-amber-950">
            <p>{result.disclaimer}</p>
            {result.warnings.map((warning, index) => (
              <p key={`${index}-${warning}`} className="mt-1">{warning}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
