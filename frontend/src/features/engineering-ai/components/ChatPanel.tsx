import { useEffect, useRef, useState } from "react";
import {
  askEngineeringAI,
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "../lib/api";
import {
  BADGE,
  BUTTON_DANGER_OUTLINE,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  FIELD_BASE,
  LABEL,
  META_TEXT,
  PANEL_ALERT,
  PANEL_EMPTY,
  SECTION_TEXT,
  SECTION_TITLE,
  SELECT_INLINE,
} from "../lib/ui";
import { ChatIcon, SearchIcon, SpinnerIcon } from "./icons";
import CitationCard from "./CitationCard";
import QuestionSuggestions from "./QuestionSuggestions";
import type { ChatMessage, Citation, Conversation } from "../types";
import type { QuestionSuggestion } from "../lib/questionSuggestions";

type Props = {
  projectId: string;
  onOpenCitation: (citation: Citation) => void;
};

export default function ChatPanel({ projectId, onOpenCitation }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState<"effective" | "history">("effective");
  const [useVision, setUseVision] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  async function loadConversations(q = search) {
    try {
      setConversations(await listConversations(projectId, q));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được lịch sử hội thoại.");
    }
  }

  useEffect(() => {
    void loadConversations("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function openConversation(id: string) {
    setBusy(true);
    setError(null);
    try {
      const conversation = await getConversation(projectId, id);
      setConversationId(conversation.id);
      setConversationTitle(conversation.title ?? null);
      setMessages(
        conversation.messages.map((message) => ({
          role: message.role === "user" ? "user" : "assistant",
          content: message.content,
          citations: message.citations ?? [],
          warnings: message.warnings ?? [],
          vision_used: message.vision_used,
          vision_note: message.vision_note,
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không mở được hội thoại.");
    } finally {
      setBusy(false);
    }
  }

  async function newConversation() {
    setBusy(true);
    setError(null);
    try {
      const created = await createConversation(projectId);
      setConversationId(created.id);
      setConversationTitle(created.title ?? null);
      setMessages([]);
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được hội thoại.");
    } finally {
      setBusy(false);
    }
  }

  async function renameCurrent() {
    if (!conversationId) return;
    const title = window.prompt("Tên hội thoại mới", conversationTitle ?? "");
    if (!title?.trim()) return;
    try {
      const updated = await renameConversation(projectId, conversationId, title.trim());
      setConversationTitle(updated.title ?? title.trim());
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đổi tên được hội thoại.");
    }
  }

  async function deleteCurrent() {
    if (!conversationId) return;
    if (!window.confirm("Xóa hội thoại này? Tài liệu và citation nguồn không bị xóa.")) {
      return;
    }
    try {
      await deleteConversation(projectId, conversationId);
      setConversationId(null);
      setConversationTitle(null);
      setMessages([]);
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xóa được hội thoại.");
    }
  }

  function pickSuggestion(suggestion: QuestionSuggestion) {
    if (busy) return;
    setInput(suggestion.prompt);
    if (suggestion.mode === "send") {
      void send(suggestion.prompt);
      return;
    }
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(
        suggestion.prompt.length,
        suggestion.prompt.length,
      );
    });
  }

  async function send(questionOverride?: string) {
    const question = (questionOverride ?? input).trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    setMessages((previous) => [
      ...previous,
      { role: "user", content: question, citations: [], warnings: [] },
    ]);
    setInput("");
    try {
      const response = await askEngineeringAI(
        projectId,
        question,
        conversationId,
        6,
        scope,
        useVision,
      );
      setConversationId(response.conversation_id);
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          warnings: response.warnings,
          confidence: response.confidence,
          no_source: response.no_source,
          vision_used: response.vision_used,
          vision_note: response.vision_note,
        },
      ]);
      await loadConversations();
      const target = response.page_action
        ? response.citations.find(
            (citation) =>
              citation.document_id === response.page_action?.document_id &&
              citation.page_number === response.page_action?.page_number,
          )
        : undefined;
      if (target) {
        onOpenCitation(target);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không gửi được câu hỏi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="min-w-0">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,17.5rem)_minmax(0,1fr)] lg:items-start">
        <aside
          aria-label="Lịch sử hội thoại"
          className={cx(CARD, "order-2 min-w-0 overflow-hidden lg:order-1")}
        >
          <div className="flex items-start justify-between gap-2 border-b border-slate-200 p-3">
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight text-slate-950">
                Lịch sử hội thoại
              </h2>
              <p className={cx(META_TEXT, "mt-0.5")}>{conversations.length} hội thoại</p>
            </div>
            <button
              type="button"
              className={cx(BUTTON_PRIMARY, "shrink-0 px-3")}
              onClick={() => void newConversation()}
              disabled={busy}
            >
              Tạo mới
            </button>
          </div>

          <form
            className="flex gap-2 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void loadConversations();
            }}
          >
            <label htmlFor="eai-conversation-search" className="sr-only">
              Tìm hội thoại
            </label>
            <input
              id="eai-conversation-search"
              className={cx(FIELD_BASE, "min-w-0 flex-1")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm hội thoại..."
            />
            <button
              type="submit"
              className={cx(BUTTON_SECONDARY, "shrink-0 px-3")}
              aria-label="Tìm hội thoại"
            >
              <SearchIcon className="h-4 w-4" />
            </button>
          </form>

          <div className="max-h-72 space-y-1 overflow-auto p-2 lg:max-h-[28rem]">
            {conversations.length === 0 && (
              <p className={cx(PANEL_EMPTY, "text-center")}>Chưa có hội thoại.</p>
            )}
            {conversations.map((conversation) => {
              const active = conversation.id === conversationId;
              return (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => void openConversation(conversation.id)}
                  aria-pressed={active}
                  className={cx(
                    "w-full min-h-11 rounded-lg p-2.5 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#405e9b]",
                    active
                      ? "bg-[#405e9b]/10 text-[#2f487a] ring-1 ring-inset ring-[#405e9b]/30"
                      : "text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <span className="block text-sm font-medium [overflow-wrap:anywhere]">
                    {conversation.title || "(không tên)"}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {conversation.messages.length} lượt
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className={cx(CARD, "order-1 min-w-0 lg:order-2")} aria-busy={busy}>
          <div className={cx(CARD_PAD, "border-b border-slate-200")}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className={SECTION_TITLE}>
                  {conversationTitle || "Hỏi đáp có citation"}
                </h2>
                <p className={cx(SECTION_TEXT, "mt-1 max-w-2xl")}>
                  Chỉ trả lời từ hồ sơ đã tải lên; hồ sơ chưa được kiểm chứng. Citation
                  bắt buộc; câu trả lời thiếu citation sẽ bị thay bằng trích dẫn trực tiếp.
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  className={cx(BUTTON_SECONDARY, "flex-1 px-3 sm:flex-none")}
                  onClick={() => void renameCurrent()}
                  disabled={!conversationId}
                >
                  Đổi tên
                </button>
                <button
                  type="button"
                  className={cx(BUTTON_DANGER_OUTLINE, "flex-1 px-3 sm:flex-none")}
                  onClick={() => void deleteCurrent()}
                  disabled={!conversationId}
                >
                  Xóa
                </button>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-slate-700">
                  Phạm vi
                  <select
                    className={SELECT_INLINE}
                    value={scope}
                    onChange={(event) =>
                      setScope(event.target.value as "effective" | "history")
                    }
                  >
                    <option value="effective">Bản có hiệu lực</option>
                    <option value="history">Toàn bộ lịch sử</option>
                  </select>
                </label>
                <label className="flex min-h-11 items-center gap-2 text-sm leading-5 text-slate-700">
                  <input
                    type="checkbox"
                    className="h-5 w-5 shrink-0 rounded border-slate-300 accent-[#405e9b]"
                    checked={useVision}
                    onChange={(event) => setUseVision(event.target.checked)}
                  />
                  Phân tích một trang top-1 (nếu Vision được cấu hình)
                </label>
              </div>
            </div>
          </div>

          <div className="space-y-3 p-4 sm:p-5">
            <div
              role="log"
              aria-live="polite"
              aria-relevant="additions"
              className="space-y-3"
            >
              {messages.length === 0 && (
                <div className={cx(PANEL_EMPTY, "flex gap-3")}>
                  <ChatIcon className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
                  <p>
                    Chọn hội thoại cũ hoặc tạo mới, sau đó hỏi tiếp. Nếu không có trang
                    nguồn, hệ thống trả: “Không tìm thấy thông tin này trong hồ sơ công
                    trình hiện có.”
                  </p>
                </div>
              )}

              {messages.map((message, index) => {
                const isUser = message.role === "user";
                return (
                  <article
                    key={`${index}-${message.role}`}
                    className={cx(
                      "max-w-full rounded-xl p-3 sm:p-4",
                      isUser
                        ? "ml-auto bg-[#405e9b] text-white sm:max-w-[85%]"
                        : "border border-slate-200 bg-slate-50/60",
                    )}
                  >
                    <div
                      className={cx(
                        "mb-1.5 flex flex-wrap items-center gap-2 text-xs font-semibold",
                        isUser ? "text-white/85" : "text-[#35507f]",
                      )}
                    >
                      <span>{isUser ? "Bạn" : "AI"}</span>
                      {message.vision_used && (
                        <span
                          className={cx(
                            BADGE,
                            "border border-violet-200 bg-violet-100 font-normal text-violet-900",
                          )}
                        >
                          Vision 1 trang
                        </span>
                      )}
                    </div>
                    <p
                      className={cx(
                        "text-sm leading-6 whitespace-pre-wrap [overflow-wrap:anywhere]",
                        isUser ? "text-white" : "text-slate-800",
                      )}
                    >
                      {message.content}
                    </p>

                    {message.no_source && (
                      <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
                        Không có trang nguồn phù hợp trong hồ sơ công trình hiện có. Không
                        có kết luận kỹ thuật nào được tạo.
                      </p>
                    )}

                    {message.vision_note && (
                      <p className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-xs leading-5 text-violet-950">
                        {message.vision_note}
                      </p>
                    )}

                    {message.citations.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-semibold text-slate-600">
                          Nguồn trích dẫn
                        </p>
                        {message.citations.map((citation) => (
                          <CitationCard
                            key={`${citation.document_id}-${citation.page_number}-${citation.chunk_id ?? ""}`}
                            citation={citation}
                            onOpen={onOpenCitation}
                          />
                        ))}
                      </div>
                    )}

                    {message.warnings.length > 0 && (
                      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-amber-800">
                        {message.warnings.map((warning, warningIndex) => (
                          <li key={`${warningIndex}-${warning}`}>{warning}</li>
                        ))}
                      </ul>
                    )}
                  </article>
                );
              })}
            </div>

            {busy && (
              <div role="status" className="flex items-center gap-2 text-sm text-slate-600">
                <SpinnerIcon className="h-4 w-4 text-[#405e9b]" />
                AI đang đối chiếu hồ sơ...
              </div>
            )}

            {error && (
              <div role="alert" className={PANEL_ALERT}>
                {error}
              </div>
            )}

            <div className="space-y-3 border-t border-slate-200 pt-4">
              <QuestionSuggestions
                busy={busy}
                compact={messages.length > 0}
                onPick={pickSuggestion}
              />
              <label htmlFor="eai-chat-input" className={LABEL}>
                Câu hỏi
              </label>
              <textarea
                ref={textareaRef}
                id="eai-chat-input"
                className={cx(FIELD, "min-h-24 resize-y")}
                rows={3}
                value={input}
                placeholder="Nhập câu hỏi về hồ sơ công trình..."
                aria-describedby="eai-chat-input-help"
                onChange={(event) => setInput(event.target.value)}
                disabled={busy}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void send();
                  }
                }}
              />
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p id="eai-chat-input-help" className={META_TEXT}>
                  Enter để gửi, Shift+Enter xuống dòng. Không tự động gửi Zalo.
                </p>
                <button
                  type="button"
                  className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
                  onClick={() => void send()}
                  disabled={busy || !input.trim()}
                >
                  {busy && <SpinnerIcon className="h-4 w-4" />}
                  Gửi
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
