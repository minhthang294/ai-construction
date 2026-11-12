import { useEffect, useRef, useState } from "react";
import { listPageExtractions, verifyPageExtraction } from "../lib/api";
import {
  isExtractionInScope,
  isStaleExtractionResponse,
} from "../lib/pageExtractionGuard";
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
  proposed: "bg-amber-100 text-amber-900",
  verified: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
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
      className="space-y-2 rounded border border-purple-200 bg-purple-50/40 p-2"
      aria-busy={loading || busy}
    >
      <div>
        <h3 className="text-xs font-semibold text-purple-950">
          Trích xuất AI cho trang (POC)
        </h3>
        <p className="text-[11px] text-purple-900">
          Dữ liệu do AI trích xuất, <strong>chưa phải dữ liệu đã xác minh</strong>. Luôn
          đối chiếu trang gốc; không tự động xác nhận.
        </p>
      </div>

      {loading && (
        <p className="text-[11px] text-gray-600">Đang tải extraction của trang...</p>
      )}
      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}
      {!loading && !error && rows.length === 0 && (
        <p className="text-[11px] text-gray-600">Chưa có extraction AI cho trang này.</p>
      )}

      {rows.map((row) => (
        <article key={row.id} className="space-y-2 rounded border border-purple-200 bg-white p-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className={`rounded px-2 py-0.5 ${STATUS_STYLE[row.status] ?? "bg-gray-100"}`}>
              {STATUS_LABEL[row.status] ?? row.status}
            </span>
            <span className="text-gray-600">
              {row.model} · {row.prompt_version} · {row.mode}
            </span>
            {row.confidence != null && (
              <span className="text-gray-600">
                confidence {Math.round(row.confidence * 100)}%
              </span>
            )}
            {row.page_sha256 && (
              <span className="text-gray-500" title={row.page_sha256}>
                sha {row.page_sha256.slice(0, 10)}…
              </span>
            )}
          </div>

          <p className="text-xs font-medium">{row.extraction.summary || "(không có summary)"}</p>
          {(row.extraction.title || row.extraction.drawing_number || row.extraction.revision) && (
            <p className="text-[11px] text-gray-600">
              {row.extraction.title || ""}
              {row.extraction.drawing_number ? ` · ${row.extraction.drawing_number}` : ""}
              {row.extraction.revision ? ` · Rev ${row.extraction.revision}` : ""}
            </p>
          )}

          {(row.extraction.key_values ?? []).length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-[11px] text-gray-800">
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
            <ul className="list-disc space-y-1 pl-5 text-[11px] text-amber-800">
              {row.warnings.map((warning, index) => (
                <li key={`${index}-${warning}`}>{warning}</li>
              ))}
            </ul>
          )}

          {row.status === "proposed" ? (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="min-h-11 min-w-28 rounded bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => void decide(row, "verified")}
                disabled={busy || loading}
              >
                Xác nhận
              </button>
              <button
                type="button"
                className="min-h-11 min-w-28 rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => void decide(row, "rejected")}
                disabled={busy || loading}
              >
                Từ chối
              </button>
            </div>
          ) : (
            <p className="text-[11px] text-gray-600">
              {row.verify_note ? `Ghi chú: ${row.verify_note}` : "Không có ghi chú xác nhận."}
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
