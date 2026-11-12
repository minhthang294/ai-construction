import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import ChatPanel from "../components/ChatPanel";
import CrossReferencePanel from "../components/CrossReferencePanel";
import DailyReportDraftPanel from "../components/DailyReportDraftPanel";
import DocumentList from "../components/DocumentList";
import DocumentUploadPanel from "../components/DocumentUploadPanel";
import InspectionChecklistPanel from "../components/InspectionChecklistPanel";
import PageViewer from "../components/PageViewer";
import PhotoSuggestionPanel from "../components/PhotoSuggestionPanel";
import VersionComparePanel from "../components/VersionComparePanel";
import {
  AlertIcon,
  ChatIcon,
  ChecklistIcon,
  CompareIcon,
  DocumentIcon,
  PhotoIcon,
  ReportIcon,
} from "../components/icons";
import { confirmEffective, fetchResourceBlob, listDocuments, reingestDocument } from "../lib/api";
import { nextTabIndex } from "../lib/tabNavigation";
import { CARD, CARD_PAD, cx, FOCUS_RING, META_TEXT } from "../lib/ui";
import type { Citation, SourceDocument } from "../types";

type Props = { projectId: string };
type Tab = "documents" | "chat" | "crossref" | "reportDraft" | "inspection" | "photos";

const TABS: Array<{ value: Tab; label: string; icon: typeof DocumentIcon }> = [
  { value: "documents", label: "Hồ sơ & trang", icon: DocumentIcon },
  { value: "chat", label: "Hỏi đáp", icon: ChatIcon },
  { value: "crossref", label: "Đối chiếu", icon: CompareIcon },
  { value: "reportDraft", label: "Báo cáo nháp", icon: ReportIcon },
  { value: "inspection", label: "Checklist", icon: ChecklistIcon },
  { value: "photos", label: "Đề xuất ảnh", icon: PhotoIcon },
];

const RETURN_LABEL: Record<Tab, string> = {
  documents: "Hồ sơ & trang",
  chat: "Hỏi đáp",
  crossref: "Đối chiếu",
  reportDraft: "Báo cáo nháp",
  inspection: "Checklist",
  photos: "Đề xuất ảnh",
};

export default function EngineeringAIPage({ projectId }: Props) {
  // Remount the complete feature on project switch so no prior-project document,
  // conversation, citation or extraction state can survive. Within one project the
  // inner state remains mounted for citation return/chat continuity.
  return <EngineeringAIProjectPage key={projectId} projectId={projectId} />;
}

function EngineeringAIProjectPage({ projectId }: Props) {
  const [tab, setTab] = useState<Tab>("documents");
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [returnTab, setReturnTab] = useState<Tab | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageViewerRef = useRef<HTMLDivElement | null>(null);
  const scrollToViewerRef = useRef(false);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

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

  useEffect(() => {
    if (!scrollToViewerRef.current) return;
    if (tab !== "documents" || !selected || selected.status !== "ready") return;
    const frame = window.requestAnimationFrame(() => {
      pageViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      scrollToViewerRef.current = false;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [tab, selectedId, pageNumber, selected?.status]);

  function selectTab(value: Tab) {
    scrollToViewerRef.current = false;
    setTab(value);
    setReturnTab(null);
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) {
    const target = nextTabIndex(currentIndex, event.key, TABS.length);
    if (target === null) return;
    event.preventDefault();
    tabRefs.current[target]?.focus();
    selectTab(TABS[target].value);
  }

  function selectDocument(document: SourceDocument) {
    scrollToViewerRef.current = false;
    setSelectedId(document.id);
    setPageNumber(1);
    setReturnTab(null);
    setTab("documents");
  }

  function openCitation(citation: Citation) {
    setReturnTab(tab !== "documents" ? tab : null);
    scrollToViewerRef.current = true;
    setSelectedId(citation.document_id);
    setPageNumber(citation.page_number);
    setTab("documents");
  }

  function closePage() {
    scrollToViewerRef.current = false;
    setSelectedId(null);
    if (returnTab) {
      setTab(returnTab);
      setReturnTab(null);
    }
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
    <div className="mx-auto w-full max-w-6xl space-y-4 sm:space-y-5">
      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex h-1.5" aria-hidden="true">
          <span className="w-4/5 bg-[#405e9b]" />
          <span className="flex-1 bg-[#e5322c]" />
        </div>
        <div className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-3xl">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#405e9b]">
                <span
                  className="inline-block h-2 w-2 rounded-full bg-[#e5322c]"
                  aria-hidden="true"
                />
                SBTECH · Kho tri thức công trình
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
                AI hồ sơ kỹ thuật
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
                Trích xuất PDF theo từng trang, OCR trang scan, tìm kiếm trong phạm vi
                công trình và trả lời kèm citation. Kho tri thức AI theo hồ sơ công trình
                chưa được kiểm chứng; không có câu trả lời kỹ thuật nào khi thiếu trang
                nguồn.
              </p>
            </div>
            <span className="inline-flex w-fit shrink-0 items-center gap-2 rounded-full border border-[#405e9b]/20 bg-[#405e9b]/5 px-3 py-1.5 text-xs font-medium text-[#35507f]">
              <DocumentIcon className="h-4 w-4" />
              Citation theo trang
            </span>
          </div>
        </div>
      </header>

      <div
        role="note"
        aria-label="Phạm vi sử dụng AI"
        className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950 sm:p-4"
      >
        <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
        <p>
          {documents.length === 0
            ? "Chưa có bản vẽ/thuyết minh trong công trình này. AI sẽ trả lời “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.” cho mọi câu hỏi kỹ thuật."
            : "Hồ sơ đã tải lên nhưng chưa được kỹ sư kiểm chứng toàn bộ. Chỉ dùng citation để đối chiếu; không coi đây là kết luận thiết kế đã xác nhận."}
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
        <div
          role="tablist"
          aria-label="Khu vực AI hồ sơ kỹ thuật"
          className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:flex lg:flex-wrap"
        >
          {TABS.map((item, index) => {
            const TabIcon = item.icon;
            const active = tab === item.value;
            return (
              <button
                key={item.value}
                ref={(node) => {
                  tabRefs.current[index] = node;
                }}
                type="button"
                role="tab"
                id={`eai-tab-${item.value}`}
                aria-selected={active}
                aria-controls={active ? `eai-panel-${item.value}` : undefined}
                tabIndex={active ? 0 : -1}
                className={cx(
                  "inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors lg:w-auto",
                  FOCUS_RING,
                  active
                    ? "bg-[#405e9b] text-white shadow-sm"
                    : "text-slate-700 hover:bg-slate-100 hover:text-[#35507f]",
                )}
                onClick={() => selectTab(item.value)}
                onKeyDown={(event) => onTabKeyDown(event, index)}
              >
                <TabIcon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </div>
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

      <div
        role="tabpanel"
        id="eai-panel-documents"
        aria-labelledby="eai-tab-documents"
        hidden={tab !== "documents"}
        className="space-y-4"
      >
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

        <div className="grid gap-4 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)] lg:items-start">
          <div className="min-w-0 space-y-4">
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
              <VersionComparePanel key={selected.id} projectId={projectId} document={selected} />
            )}
          </div>

          <div ref={pageViewerRef} className="min-w-0 scroll-mt-4 space-y-4">
            {selected && selected.status === "ready" ? (
              <PageViewer
                projectId={projectId}
                documentId={selected.id}
                pageNumber={pageNumber}
                totalPages={Math.max(selected.page_count, 1)}
                onClose={closePage}
                onPageChange={setPageNumber}
                closeLabel={returnTab ? `Quay lại ${RETURN_LABEL[returnTab]}` : "Đóng"}
              />
            ) : selected ? (
              <div
                className={cx(
                  CARD,
                  CARD_PAD,
                  "flex gap-3",
                  selected.status === "failed"
                    ? "border-red-200 bg-red-50"
                    : "border-amber-200 bg-amber-50",
                )}
              >
                <AlertIcon
                  className={cx(
                    "mt-0.5 h-5 w-5 shrink-0",
                    selected.status === "failed" ? "text-red-700" : "text-amber-700",
                  )}
                />
                <p
                  className={cx(
                    "text-sm leading-6",
                    selected.status === "failed" ? "text-red-900" : "text-amber-950",
                  )}
                >
                  {selected.status === "failed"
                    ? "Hồ sơ xử lý lỗi. Kiểm tra cảnh báo và thử xử lý lại từ danh sách hồ sơ."
                    : "Hồ sơ đang được trích xuất/OCR. Trang sẽ mở được khi trạng thái là ready."}
                </p>
              </div>
            ) : documents.length > 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-center sm:p-8">
                <DocumentIcon className="mx-auto h-10 w-10 text-slate-300" />
                <h2 className="mt-3 text-base font-semibold text-slate-900">
                  Chọn một hồ sơ để xem trang
                </h2>
                <p className={cx(META_TEXT, "mx-auto mt-1 max-w-md")}>
                  Mở trang nguồn, text trích xuất và dữ liệu AI đã đề xuất cho hồ sơ đang
                  chọn. Citation từ Hỏi đáp hoặc Đối chiếu cũng sẽ mở đúng trang tại đây.
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div
        role="tabpanel"
        id="eai-panel-chat"
        aria-labelledby="eai-tab-chat"
        hidden={tab !== "chat"}
      >
        <ChatPanel key={projectId} projectId={projectId} onOpenCitation={openCitation} />
      </div>

      {tab === "crossref" && (
        <div role="tabpanel" id="eai-panel-crossref" aria-labelledby="eai-tab-crossref">
          <CrossReferencePanel
            projectId={projectId}
            documents={documents}
            onOpenCitation={openCitation}
          />
        </div>
      )}

      {tab === "reportDraft" && (
        <div
          role="tabpanel"
          id="eai-panel-reportDraft"
          aria-labelledby="eai-tab-reportDraft"
        >
          <DailyReportDraftPanel projectId={projectId} />
        </div>
      )}

      {tab === "inspection" && (
        <div
          role="tabpanel"
          id="eai-panel-inspection"
          aria-labelledby="eai-tab-inspection"
        >
          <InspectionChecklistPanel
            projectId={projectId}
            onOpenCitation={openCitation}
          />
        </div>
      )}

      {tab === "photos" && (
        <div role="tabpanel" id="eai-panel-photos" aria-labelledby="eai-tab-photos">
          <PhotoSuggestionPanel projectId={projectId} />
        </div>
      )}
    </div>
  );
}
