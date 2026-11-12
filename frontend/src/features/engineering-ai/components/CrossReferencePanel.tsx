import { useEffect, useMemo, useState } from "react";
import { crossReference } from "../lib/api";
import {
  BADGE,
  BUTTON_PRIMARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  FIELD_INLINE,
  LABEL,
  META_TEXT,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { AlertIcon, CompareIcon, SpinnerIcon } from "./icons";
import CitationCard from "./CitationCard";
import type { Citation, CrossReferenceResponse, SourceDocument } from "../types";

type Props = {
  projectId: string;
  documents: SourceDocument[];
  onOpenCitation: (citation: Citation) => void;
};

type PageChoice = { documentId: string; pageNumber: number };

export default function CrossReferencePanel({
  projectId,
  documents,
  onOpenCitation,
}: Props) {
  const ready = useMemo(
    () => documents.filter((document) => document.status === "ready" && document.page_count > 0),
    [documents],
  );
  const [first, setFirst] = useState<PageChoice>({ documentId: "", pageNumber: 1 });
  const [second, setSecond] = useState<PageChoice>({ documentId: "", pageNumber: 1 });
  const [topic, setTopic] = useState("");
  const [result, setResult] = useState<CrossReferenceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready.length === 0) return;
    setFirst((current) => {
      if (ready.some((document) => document.id === current.documentId)) return current;
      return { documentId: ready[0].id, pageNumber: 1 };
    });
    setSecond((current) => {
      if (ready.some((document) => document.id === current.documentId)) return current;
      const candidate = ready[1] ?? ready[0];
      return { documentId: candidate.id, pageNumber: 1 };
    });
  }, [ready]);

  function pageLimit(documentId: string): number {
    const document = ready.find((item) => item.id === documentId);
    return Math.max(document?.page_count ?? 1, 1);
  }

  function updatePage(
    setter: (value: PageChoice) => void,
    current: PageChoice,
    patch: Partial<PageChoice>,
  ) {
    const next = { ...current, ...patch };
    next.pageNumber = Math.max(1, Math.min(next.pageNumber || 1, pageLimit(next.documentId)));
    setter(next);
    setResult(null);
    setError(null);
  }

  async function compare() {
    if (!first.documentId || !second.documentId || busy) return;
    if (
      first.documentId === second.documentId &&
      first.pageNumber === second.pageNumber
    ) {
      setError("Hai trang đối chiếu phải khác nhau.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await crossReference(
        projectId,
        { document_id: first.documentId, page_number: first.pageNumber },
        { document_id: second.documentId, page_number: second.pageNumber },
        topic,
      );
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đối chiếu được hai trang.");
    } finally {
      setBusy(false);
    }
  }

  if (ready.length === 0) {
    return (
      <section className={cx(CARD, CARD_PAD, "flex gap-3")}>
        <CompareIcon className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
        <p className={SECTION_TEXT}>
          Cần ít nhất một hồ sơ PDF ở trạng thái ready để đối chiếu hai trang. Chưa có
          nguồn thì không tạo kết luận kỹ thuật.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div className="max-w-3xl">
        <h2 className={SECTION_TITLE}>Đối chiếu chéo hai trang</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          Chỉ nêu điểm nghi vấn khi hai câu có cùng chủ đề và giá trị số/đơn vị/cấp
          khác nhau. Kết quả luôn kèm hai citation và không kết luận trang nào đúng
          hay thiết kế sai.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <PageSelector
          id="eai-crossref-first"
          label="Trang thứ nhất"
          documents={ready}
          value={first}
          onChange={(patch) => updatePage(setFirst, first, patch)}
        />
        <PageSelector
          id="eai-crossref-second"
          label="Trang thứ hai"
          documents={ready}
          value={second}
          onChange={(patch) => updatePage(setSecond, second, patch)}
        />
      </div>

      <label className={LABEL} htmlFor="eai-crossref-topic">
        Chủ đề cần đối chiếu (không bắt buộc)
        <input
          id="eai-crossref-topic"
          className={FIELD}
          value={topic}
          onChange={(event) => {
            setTopic(event.target.value);
            setResult(null);
          }}
          placeholder="Ví dụ: lớp bê tông bảo vệ, cao độ đỉnh trụ..."
        />
      </label>

      <button
        type="button"
        className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
        onClick={() => void compare()}
        disabled={busy || !first.documentId || !second.documentId}
      >
        {busy && <SpinnerIcon className="h-4 w-4" />}
        {busy ? "Đang đối chiếu..." : "Đối chiếu hai trang"}
      </button>

      {error && (
        <div role="alert" className={PANEL_ALERT}>
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
            <p className="flex items-center gap-2 font-semibold">
              <AlertIcon className="h-4 w-4 shrink-0" />
              Trạng thái: cần kỹ sư kiểm tra
            </p>
            <p className="mt-1">{result.message}</p>
            <p className="mt-1 font-medium">{result.disclaimer}</p>
            {result.warnings.map((warning, index) => (
              <p key={`${index}-${warning}`} className="mt-1">
                {warning}
              </p>
            ))}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-slate-800">Hai trang đã đối chiếu</h3>
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {result.citations.map((citation, index) => (
                <CitationCard
                  key={`top-${citation.document_id}-${citation.page_number}-${index}`}
                  citation={citation}
                  onOpen={onOpenCitation}
                />
              ))}
            </div>
          </div>

          {result.suggestions.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              Không có điểm nghi vấn được tạo. Điều này không có nghĩa hai trang đã đồng
              nhất hoặc hồ sơ đã được duyệt.
            </p>
          ) : (
            result.suggestions.map((suggestion, index) => (
              <article
                key={`${index}-${suggestion.topic}`}
                className="space-y-3 rounded-lg border border-amber-200 bg-white p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-amber-950">
                    Điểm nghi vấn {index + 1}: {suggestion.topic}
                  </h3>
                  <span className={cx(BADGE, "border border-amber-200 bg-amber-100 text-amber-900")}>
                    độ khớp văn bản {Math.round(suggestion.confidence * 100)}%
                  </span>
                </div>
                <p className="text-sm leading-6 text-slate-800">{suggestion.observation}</p>
                <div className="grid gap-2 md:grid-cols-2">
                  <CitationCard
                    citation={suggestion.first_citation}
                    onOpen={onOpenCitation}
                  />
                  <CitationCard
                    citation={suggestion.second_citation}
                    onOpen={onOpenCitation}
                  />
                </div>
                {suggestion.warnings.map((warning, warningIndex) => (
                  <p key={`${warningIndex}-${warning}`} className="text-xs leading-5 text-red-700">
                    {warning}
                  </p>
                ))}
              </article>
            ))
          )}
        </div>
      )}
    </section>
  );
}

function PageSelector({
  id,
  label,
  documents,
  value,
  onChange,
}: {
  id: string;
  label: string;
  documents: SourceDocument[];
  value: PageChoice;
  onChange: (patch: Partial<PageChoice>) => void;
}) {
  const selected = documents.find((document) => document.id === value.documentId);
  const maxPage = Math.max(selected?.page_count ?? 1, 1);
  return (
    <fieldset className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <legend className="px-1 text-sm font-semibold text-slate-800">{label}</legend>
      <label className="mt-1 block text-sm font-medium text-slate-700" htmlFor={`${id}-document`}>
        Hồ sơ
        <select
          id={`${id}-document`}
          className={cx(FIELD_INLINE, "mt-1.5 w-full")}
          value={value.documentId}
          onChange={(event) => onChange({ documentId: event.target.value, pageNumber: 1 })}
        >
          {documents.map((document) => (
            <option key={document.id} value={document.id}>
              {document.original_name} (v{document.version}, {document.page_count} trang)
            </option>
          ))}
        </select>
      </label>
      <label
        className="mt-3 flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700"
        htmlFor={`${id}-page`}
      >
        Trang
        <input
          id={`${id}-page`}
          type="number"
          inputMode="numeric"
          min={1}
          max={maxPage}
          className={cx(FIELD_INLINE, "w-24")}
          value={value.pageNumber}
          onChange={(event) => onChange({ pageNumber: Number(event.target.value) })}
        />
        <span className={cx(META_TEXT, "tabular-nums")}>/ {maxPage}</span>
      </label>
    </fieldset>
  );
}
