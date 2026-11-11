import { useEffect, useState } from "react";
import {
  askEngineeringAI,
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "../lib/api";
import type { ChatMessage, Citation, Conversation } from "../types";
import CitationCard from "./CitationCard";

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

  async function send() {
    const question = input.trim();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không gửi được câu hỏi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-2 rounded border border-gray-200 bg-white p-2 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Lịch sử hội thoại</h2>
            <button
              type="button"
              className="rounded bg-blue-600 px-2 py-1 text-[11px] font-semibold text-white"
              onClick={() => void newConversation()}
            >
              Mới
            </button>
          </div>
          <div className="flex gap-1">
            <input
              className="min-w-0 flex-1 rounded border border-gray-300 p-1.5 text-xs"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tìm hội thoại..."
            />
            <button
              type="button"
              className="rounded border border-gray-300 px-2 text-xs"
              onClick={() => void loadConversations()}
            >
              Tìm
            </button>
          </div>
          <div className="max-h-80 space-y-1 overflow-auto">
            {conversations.length === 0 && (
              <p className="p-2 text-xs text-gray-500">Chưa có hội thoại.</p>
            )}
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => void openConversation(conversation.id)}
                className={`w-full rounded p-2 text-left text-xs ${
                  conversation.id === conversationId ? "bg-blue-50" : "hover:bg-gray-50"
                }`}
              >
                <span className="block font-medium">
                  {conversation.title || "(không tên)"}
                </span>
                <span className="text-[11px] text-gray-500">
                  {conversation.messages.length} lượt
                </span>
              </button>
            ))}
          </div>
        </aside>

        <div className="space-y-3 rounded border border-gray-200 bg-white p-3 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">
                {conversationTitle || "Hỏi đáp có citation"}
              </h2>
              <p className="text-xs text-gray-600">
                Chỉ trả lời từ hồ sơ đã tải lên; hồ sơ chưa được kiểm chứng. Citation
                bắt buộc; câu trả lời thiếu citation sẽ bị thay bằng trích dẫn trực tiếp.
              </p>
            </div>
            <div className="flex gap-1">
              <button
                type="button"
                className="rounded border border-gray-300 px-2 py-1 text-[11px] disabled:opacity-40"
                onClick={() => void renameCurrent()}
                disabled={!conversationId}
              >
                Đổi tên
              </button>
              <button
                type="button"
                className="rounded border border-red-300 px-2 py-1 text-[11px] text-red-700 disabled:opacity-40"
                onClick={() => void deleteCurrent()}
                disabled={!conversationId}
              >
                Xóa
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 rounded bg-gray-50 p-2 text-xs">
            <label className="flex items-center gap-2">
              Phạm vi
              <select
                className="rounded border border-gray-300 p-1"
                value={scope}
                onChange={(event) =>
                  setScope(event.target.value as "effective" | "history")
                }
              >
                <option value="effective">Bản có hiệu lực</option>
                <option value="history">Toàn bộ lịch sử</option>
              </select>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={useVision}
                onChange={(event) => setUseVision(event.target.checked)}
              />
              Phân tích một trang top-1 (nếu Vision được cấu hình)
            </label>
          </div>

          <div className="space-y-3">
            {messages.length === 0 && (
              <div className="rounded bg-gray-50 p-3 text-xs text-gray-600">
                Chọn hội thoại cũ hoặc tạo mới, sau đó hỏi tiếp. Nếu không có trang nguồn,
                hệ thống trả: “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.”
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={`${index}-${message.role}`}
                className={`rounded p-2 ${
                  message.role === "user" ? "bg-gray-100" : "border border-gray-200 bg-white"
                }`}
              >
                <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] font-semibold text-gray-600">
                  <span>{message.role === "user" ? "Bạn" : "AI"}</span>
                  {message.role === "assistant" && message.confidence != null && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 font-normal">
                      độ khớp nguồn {Math.round(message.confidence * 100)}%
                    </span>
                  )}
                  {message.vision_used && (
                    <span className="rounded bg-purple-100 px-1.5 py-0.5 font-normal text-purple-800">
                      Vision 1 trang
                    </span>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm">{message.content}</p>

                {message.no_source && (
                  <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-900">
                    Không có trang nguồn phù hợp trong hồ sơ công trình hiện có. Không có
                    kết luận kỹ thuật nào được tạo.
                  </p>
                )}

                {message.vision_note && (
                  <p className="mt-2 rounded bg-purple-50 p-2 text-xs text-purple-900">
                    {message.vision_note}
                  </p>
                )}

                {message.citations.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <p className="text-[11px] font-semibold text-gray-600">Nguồn trích dẫn</p>
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
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px] text-amber-800">
                    {message.warnings.map((warning, warningIndex) => (
                      <li key={`${warningIndex}-${warning}`}>{warning}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {busy && <div className="text-xs text-gray-600">AI đang đối chiếu hồ sơ...</div>}
          </div>

          {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

          <div className="space-y-2">
            <textarea
              className="w-full rounded border border-gray-300 p-2 text-sm"
              rows={3}
              value={input}
              placeholder="Nhập câu hỏi về hồ sơ công trình..."
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] text-gray-500">
                Enter để gửi, Shift+Enter xuống dòng. Không tự động gửi Zalo.
              </p>
              <button
                type="button"
                className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => void send()}
                disabled={busy || !input.trim()}
              >
                Gửi
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
