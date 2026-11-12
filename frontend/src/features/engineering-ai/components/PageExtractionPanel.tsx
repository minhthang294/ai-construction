import { useEffect, useRef, useState } from "react";
import { listPageExtractions, verifyPageExtraction } from "../lib/api";
import {
  isExtractionInScope,
  isStaleExtractionResponse,
} from "../lib/pageExtractionGuard";
import {
  BADGE,
  BUTTON_DANGER,
  BUTTON_SUCCESS,
  cx,
  META_TEXT,
  PANEL_ALERT,
} from "../lib/ui";
import { AlertIcon, CheckIcon, XIcon } from "./icons";
import type { PageExtractionRecord } from "../types";

type Props = {
  projectId: string;
  documentId: string;
  pageNumber: number;
};

const STATUS_LABEL: Record<string, string> = {
  proposed: "Đề xuất — chưa xác nhận",
  verified: "Đã xác nhận",
  rejected: "Đã từ chối",
};

const STATUS_STYLE: Record<string, string> = {
  proposed: "border-amber-200 bg-amber-100 text-amber-900",
  verified: "border-emerald-200 bg-emerald-100 text-emerald-900",
  rejected: "border-red-200 bg-red-100 text-red-800",
};

export default function PageExtractionPanel({
  projectId,
  documentId,
  pageNumber,
}: Props) {
  const [rows, setRows] = useState<PageExtractionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const requestId = ++requestIdRef.current;
    // Never show the previous page's extraction while the new request runs.
    setRows([]);
    setLoading(true);
    setError(null);

    listPageExtractions(projectId, documentId, pageNumber)
      .then((data) => {
        if (
          cancelled ||
          isStaleExtractionResponse(requestId, requestIdRef.current)
        ) {
          return;
        }
        setRows(
          data.filter((row) =>
            isExtractionInScope(row, projectId, documentId, pageNumber),
          ),
        );
      })
      .catch((err) => {
        if (
          cancelled ||
          isStaleExtractionResponse(requestId, requestIdRef.current)
        ) {
          return;
        }
        setError(
          err instanceof Error ? err.message : "Không tải được extraction.",
        );
      })
      .finally(() => {
        if (
          cancelled ||
          isStaleExtractionResponse(requestId, requestIdRef.current)
        ) {
          return;
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
      requestIdRef.current += 1;
    };
  }, [projectId, documentId, pageNumber]);

  async function decide(
    row: PageExtractionRecord,
    status: "verified" | "rejected",
  ) {
    if (busy || loading) return;
    if (!isExtractionInScope(row, projectId, documentId, pageNumber)) {
      setError("Extraction không còn thuộc trang hiện tại; đã bỏ qua thao tác.");
      return;
    }
    const requestId = requestIdRef.current;
    const note = window.prompt(
      status === "verified"
        ? "Ghi chú xác nhận (đã đối chiếu trang gốc):"
        : "Lý do từ chối:",
    );
    if (note === null) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await verifyPageExtraction(
        projectId,
        row.id,
        status,
        note.trim() || undefined,
      );
      if (isStaleExtractionResponse(requestId, requestIdRef.current)) {
        return;
      }
      setRows((previous) =>
        previous.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      if (!isStaleExtractionResponse(requestId, requestIdRef.current)) {
        setError(
          err instanceof Error ? err.message : "Không cập nhật được trạng thái.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-busy={loading || busy}
      className="space-y-3 rounded-lg border border-[#405e9b]/20 bg-[#405e9b]/5 p-3"
    >
      <div>
        <h3 className="text-sm font-semibold text-[#2f487a]">
          Trích xuất AI cho trang (POC)
        </h3>
        <p className="mt-1 text-xs leading-5 text-slate-700">
          Dữ liệu do AI trích xuất, <strong>chưa phải dữ liệu đã xác minh</strong>. Luôn
          đối chiếu trang gốc; không tự động xác nhận.
        </p>
      </div>

      {loading && (
        <p role="status" className="text-xs leading-5 text-slate-600">
          Đang tải extraction của trang...
        </p>
      )}
      {error && (
        <div role="alert" className={PANEL_ALERT}>
          {error}
        </div>
      )}
      {!loading && !error && rows.length === 0 && (
        <p className="text-xs leading-5 text-slate-600">
          Chưa có extraction AI cho trang này.
        </p>
      )}

      {rows.map((row) => (
        <article
          key={row.id}
          className="space-y-3 rounded-lg border border-slate-200 bg-white p-3"
        >
          <div className="flex flex-wrap items-center gap-2 text-xs leading-5">
            <span
              className={cx(
                BADGE,
                STATUS_STYLE[row.status] ??
                  "border border-slate-200 bg-slate-100 text-slate-700",
              )}
            >
              {STATUS_LABEL[row.status] ?? row.status}
            </span>
            <span className="text-slate-600">
              {row.model} · {row.prompt_version} · {row.mode}
            </span>
            {row.confidence != null && (
              <span className="text-slate-600">
                confidence {Math.round(row.confidence * 100)}%
              </span>
            )}
            {row.page_sha256 && (
              <span className="font-mono text-slate-500" title={row.page_sha256}>
                sha {row.page_sha256.slice(0, 10)}…
              </span>
            )}
          </div>

          <p className="text-sm font-medium leading-6 text-slate-900">
            {row.extraction.summary || "(không có summary)"}
          </p>
          {(row.extraction.title || row.extraction.drawing_number || row.extraction.revision) && (
            <p className={cx(META_TEXT, "[overflow-wrap:anywhere]")}>
              {row.extraction.title || ""}
              {row.extraction.drawing_number ? ` · ${row.extraction.drawing_number}` : ""}
              {row.extraction.revision ? ` · Rev ${row.extraction.revision}` : ""}
            </p>
          )}

          {(row.extraction.key_values ?? []).length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-800">
              {(row.extraction.key_values ?? []).map((item, index) => (
                <li key={`${index}-${item.name}-${item.value}`}>
                  <span className="font-medium">{item.name}</span>: {item.value}
                  {item.unit ? ` ${item.unit}` : ""}
                  {item.quote ? ` — “${item.quote}”` : ""}
                </li>
              ))}
            </ul>
          )}

          {row.warnings.length > 0 && (
            <ul className="space-y-1 rounded-lg bg-amber-50 p-2 text-xs leading-5 text-amber-900">
              {row.warnings.map((warning, index) => (
                <li key={`${index}-${warning}`} className="flex items-start gap-1.5">
                  <AlertIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {warning}
                </li>
              ))}
            </ul>
          )}

          {row.status === "proposed" ? (
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <button
                type="button"
                className={cx(BUTTON_DANGER, "w-full sm:w-auto")}
                onClick={() => void decide(row, "rejected")}
                disabled={busy || loading}
              >
                <XIcon className="h-4 w-4" />
                Từ chối
              </button>
              <button
                type="button"
                className={cx(BUTTON_SUCCESS, "w-full sm:w-auto")}
                onClick={() => void decide(row, "verified")}
                disabled={busy || loading}
              >
                <CheckIcon className="h-4 w-4" />
                Xác nhận
              </button>
            </div>
          ) : (
            <p className="text-xs leading-5 text-slate-600">
              {row.verify_note ? `Ghi chú: ${row.verify_note}` : "Không có ghi chú xác nhận."}
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
