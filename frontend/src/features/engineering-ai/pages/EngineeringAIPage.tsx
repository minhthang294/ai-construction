import { useCallback, useEffect, useRef, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import DocumentList from "../components/DocumentList";
import PageViewer from "../components/PageViewer";
import { AlertIcon, ChatIcon, DocumentIcon } from "../components/icons";
import { fetchResourceBlob, listDocuments, listQuestionSuggestions } from "../lib/api";
import { cx, META_TEXT } from "../lib/ui";
import type { Citation, QuestionSuggestion, SourceDocument } from "../types";

type Props = { projectId: string };

export default function EngineeringAIPage({ projectId }: Props) {
  // Remount on project switch so no prior-project document/source state survives.
  return <EngineeringAIProjectPage key={projectId} projectId={projectId} />;
}

function EngineeringAIProjectPage({ projectId }: Props) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [suggestions, setSuggestions] = useState<QuestionSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageViewerRef = useRef<HTMLDivElement | null>(null);
  const scrollToViewerRef = useRef(false);

  const refresh = useCallback(
    async (showLoading = false) => {
      if (showLoading) setLoading(true);
      try {
        const result = await listDocuments(projectId, true);
        setDocuments(result);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Không tải được danh sách hồ sơ.");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    void refresh(true);
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    setSuggestionsLoading(true);
    listQuestionSuggestions(projectId)
      .then((rows) => {
        if (!cancelled) setSuggestions(rows);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setSuggestionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const selected = documents.find((document) => document.id === selectedId) ?? null;

  useEffect(() => {
    if (!scrollToViewerRef.current) return;
    if (!selected) return;
    const frame = window.requestAnimationFrame(() => {
      pageViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      scrollToViewerRef.current = false;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [selectedId, pageNumber, selected]);

  function selectDocument(document: SourceDocument) {
    scrollToViewerRef.current = true;
    setSelectedId(document.id);
    setPageNumber(1);
  }

  function openCitation(citation: Citation) {
    if (!citation.document_id || citation.page_number < 1) return;
    scrollToViewerRef.current = true;
    setSelectedId(citation.document_id);
    setPageNumber(citation.page_number);
  }

  function openComponent(recordId: string, citation: Citation) {
    // The app shell can listen and route to the component screen; this module
    // only emits the event because navigation is owned outside engineering-ai.
    window.dispatchEvent(
      new CustomEvent("engineering-ai:open-component", {
        detail: { projectId, recordId, citation },
      }),
    );
  }

  function closePage() {
    scrollToViewerRef.current = false;
    setSelectedId(null);
  }

  async function openOriginal(document: SourceDocument) {
    if (!document.original_url) return;
    const popup = window.open("", "_blank");
    try {
      const blob = await fetchResourceBlob(document.original_url);
      const url = URL.createObjectURL(blob);
      if (popup) popup.location.href = url;
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      popup?.close();
      setError(err instanceof Error ? err.message : "Không mở được PDF gốc.");
    }
  }

  return (
    <div className="w-full space-y-3 sm:space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-slate-950 sm:text-xl">
            Hỏi AI hồ sơ kỹ thuật
          </h1>
        </div>
        <span className="inline-flex w-fit shrink-0 items-center gap-2 rounded-full border border-[#405e9b]/20 bg-[#405e9b]/5 px-3 py-1.5 text-sm font-medium text-[#35507f]">
          <ChatIcon className="h-4 w-4" />
          Trả lời có nguồn
        </span>
      </header>

      <div
        role="note"
        aria-label="Phạm vi sử dụng AI"
        className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950"
      >
        <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
        <p>
          {suggestionsLoading && documents.length === 0
            ? "Đang kiểm tra dữ liệu cấu kiện và tiến độ của công trình..."
            : documents.length > 0
              ? "Dữ kiện AI trích xuất chưa được kiểm chứng toàn bộ. Tiến độ thi công không phải nghiệm thu; chỉ dùng nguồn trích dẫn để đối chiếu bản vẽ gốc."
              : suggestions.length > 0
                ? "Chưa có bản vẽ nguồn, nhưng AI vẫn trả lời được từ database cấu kiện và tiến độ. Thiếu dữ kiện thì trả câu từ chối chuẩn."
                : "Chưa có dữ liệu cấu kiện, tiến độ hay bản vẽ nguồn. AI sẽ trả lời “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.”"}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-800"
        >
          <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-red-700" />
          <p className="min-w-0 [overflow-wrap:anywhere]">{error}</p>
        </div>
      )}

      {selected && (
        <div ref={pageViewerRef} className="min-w-0 scroll-mt-4">
          <PageViewer
            key={`${selected.id}:${pageNumber}`}
            projectId={projectId}
            documentId={selected.id}
            pageNumber={pageNumber}
            totalPages={Math.max(selected.page_count, 1)}
            onClose={closePage}
            onPageChange={setPageNumber}
            closeLabel="Đóng bản vẽ"
          />
        </div>
      )}

      <ChatPanel
        key={projectId}
        projectId={projectId}
        suggestions={suggestions}
        suggestionsLoading={suggestionsLoading}
        onOpenCitation={openCitation}
        onOpenComponent={openComponent}
      />

      <details className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm sm:p-4">
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-slate-800">
          <DocumentIcon className="h-4 w-4 text-[#405e9b]" />
          Hồ sơ nguồn ({documents.length})
          <span className={cx(META_TEXT, "ml-auto font-normal")}>Chỉ đọc</span>
        </summary>
        <div className="mt-3">
          <DocumentList
            documents={documents}
            selectedId={selectedId}
            onSelect={selectDocument}
            onRefresh={() => void refresh(true)}
            onOpenOriginal={(document) => void openOriginal(document)}
            loading={loading}
          />
        </div>
      </details>
    </div>
  );
}
