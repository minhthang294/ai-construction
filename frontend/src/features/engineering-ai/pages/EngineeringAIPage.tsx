import { useCallback, useEffect, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import CrossReferencePanel from "../components/CrossReferencePanel";
import DailyReportDraftPanel from "../components/DailyReportDraftPanel";
import DocumentList from "../components/DocumentList";
import DocumentUploadPanel from "../components/DocumentUploadPanel";
import InspectionChecklistPanel from "../components/InspectionChecklistPanel";
import PageViewer from "../components/PageViewer";
import PhotoSuggestionPanel from "../components/PhotoSuggestionPanel";
import VersionComparePanel from "../components/VersionComparePanel";
import { confirmEffective, fetchResourceBlob, listDocuments, reingestDocument } from "../lib/api";
import type { Citation, SourceDocument } from "../types";

type Props = { projectId: string };
type Tab = "documents" | "chat" | "crossref" | "reportDraft" | "inspection" | "photos";

export default function EngineeringAIPage({ projectId }: Props) {
  const [tab, setTab] = useState<Tab>("documents");
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const hasPending = documents.some(
    (document) =>
      document.status === "pending" ||
      document.status === "running" ||
      document.status === "ocr_completed" ||
      document.status === "indexing",
  );

  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(() => {
      void refresh(false);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasPending, refresh]);

  const selected = documents.find((document) => document.id === selectedId) ?? null;

  function selectDocument(document: SourceDocument) {
    setSelectedId(document.id);
    setPageNumber(1);
    setTab("documents");
  }

  function openCitation(citation: Citation) {
    setSelectedId(citation.document_id);
    setPageNumber(citation.page_number);
    setTab("documents");
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

  async function reingest(document: SourceDocument) {
    try {
      await reingestDocument(projectId, document.id);
      setError(null);
      await refresh(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xử lý lại được hồ sơ.");
    }
  }

  async function makeEffective(document: SourceDocument) {
    const note = window.prompt(
      `Ghi chú xác nhận hiệu lực cho ${document.original_name} v${document.version}`,
    );
    if (!note?.trim()) return;
    try {
      await confirmEffective(projectId, document.id, note.trim());
      setError(null);
      await refresh(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xác nhận được hiệu lực.");
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 bg-gray-100 p-3">
      <header className="space-y-1">
        <h1 className="text-xl font-bold">AI hồ sơ kỹ thuật</h1>
        <p className="text-xs text-gray-700">
          Trích xuất PDF theo từng trang, OCR trang scan, tìm kiếm trong phạm vi công
          trình và trả lời kèm citation. Kho tri thức AI theo hồ sơ công trình chưa được
          kiểm chứng; không có câu trả lời kỹ thuật nào khi thiếu trang nguồn.
        </p>
      </header>

      <div className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
        {documents.length === 0
          ? "Chưa có bản vẽ/thuyết minh trong công trình này. AI sẽ trả lời “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.” cho mọi câu hỏi kỹ thuật."
          : "Hồ sơ đã tải lên nhưng chưa được kỹ sư kiểm chứng toàn bộ. Chỉ dùng citation để đối chiếu; không coi đây là kết luận thiết kế đã xác nhận."}
      </div>

      <nav className="flex flex-wrap gap-2">
        {(
          [
            ["documents", "Hồ sơ & trang"],
            ["chat", "Hỏi đáp"],
            ["crossref", "Đối chiếu"],
            ["reportDraft", "Báo cáo nháp"],
            ["inspection", "Checklist"],
            ["photos", "Đề xuất ảnh"],
          ] as Array<[Tab, string]>
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`rounded px-3 py-2 text-sm font-medium ${
              tab === value ? "bg-blue-600 text-white" : "border border-gray-300 bg-white"
            }`}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </nav>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {tab === "documents" && (
        <div className="space-y-3">
          <DocumentUploadPanel
            projectId={projectId}
            onUploaded={(document) => {
              setDocuments((previous) => {
                const others = previous.filter((item) => item.id !== document.id);
                return [document, ...others];
              });
              setSelectedId(document.id);
              setPageNumber(1);
              void refresh(false);
            }}
          />
          <DocumentList
            documents={documents}
            selectedId={selectedId}
            onSelect={selectDocument}
            onRefresh={() => void refresh(true)}
            onOpenOriginal={(document) => void openOriginal(document)}
            onReingest={(document) => void reingest(document)}
            onConfirmEffective={(document) => void makeEffective(document)}
            loading={loading}
          />
          {selected && selected.status === "ready" && (
            <VersionComparePanel projectId={projectId} document={selected} />
          )}
          {selected && selected.status === "ready" && (
            <PageViewer
              projectId={projectId}
              documentId={selected.id}
              pageNumber={pageNumber}
              totalPages={Math.max(selected.page_count, 1)}
              onClose={() => setSelectedId(null)}
              onPageChange={setPageNumber}
            />
          )}
          {selected && selected.status !== "ready" && (
            <div className="rounded border border-gray-200 bg-white p-3 text-xs text-gray-700">
              {selected.status === "failed"
                ? "Hồ sơ xử lý lỗi. Kiểm tra cảnh báo và thử xử lý lại từ danh sách hồ sơ."
                : "Hồ sơ đang được trích xuất/OCR. Trang sẽ mở được khi trạng thái là ready."}
            </div>
          )}
        </div>
      )}

      {tab === "chat" && (
        <ChatPanel projectId={projectId} onOpenCitation={openCitation} />
      )}

      {tab === "crossref" && (
        <CrossReferencePanel
          projectId={projectId}
          documents={documents}
          onOpenCitation={openCitation}
        />
      )}

      {tab === "reportDraft" && <DailyReportDraftPanel projectId={projectId} />}

      {tab === "inspection" && (
        <InspectionChecklistPanel
          projectId={projectId}
          onOpenCitation={openCitation}
        />
      )}

      {tab === "photos" && <PhotoSuggestionPanel projectId={projectId} />}
    </div>
  );
}
