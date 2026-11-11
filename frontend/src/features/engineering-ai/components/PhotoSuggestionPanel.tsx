import { useState } from "react";
import { suggestPhoto } from "../lib/api";
import type { PhotoSuggestion } from "../types";

type Props = {
  projectId: string;
};

export default function PhotoSuggestionPanel({ projectId }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<PhotoSuggestion | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function choose(next: File | null) {
    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setSuggestion(null);
    setConfirmed(false);
    setCaption("");
    setError(null);
    setPreview(next ? URL.createObjectURL(next) : null);
  }

  async function suggest() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await suggestPhoto(projectId, file);
      setSuggestion(result);
      setCaption(result.suggested_caption ?? "");
      setConfirmed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được đề xuất.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded border border-gray-200 bg-white p-3 shadow-sm space-y-3">
      <div>
        <h2 className="text-sm font-semibold">Đề xuất ảnh hiện trường</h2>
        <p className="text-xs text-gray-600">
          AI chỉ đề xuất loại ảnh/caption/vùng cần xem. Không tự ghi vào hồ sơ, không
          suy đoán GPS, kích thước, khối lượng hay nghiệm thu.
        </p>
      </div>

      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="block w-full text-xs"
        onChange={(event) => choose(event.target.files?.[0] ?? null)}
      />

      {preview && (
        <img
          src={preview}
          alt="Ảnh xem trước"
          className="max-h-64 rounded border border-gray-200 object-contain"
        />
      )}

      <button
        type="button"
        className="rounded bg-gray-800 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
        onClick={() => void suggest()}
        disabled={!file || busy}
      >
        {busy ? "Đang phân tích..." : "Đề xuất bằng AI"}
      </button>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {suggestion && (
        <div className="space-y-2 rounded bg-amber-50 p-2 text-xs text-amber-950">
          <p className="font-semibold">Đề xuất chưa được xác nhận</p>
          <div className="grid gap-1 sm:grid-cols-2">
            <p>Loại ảnh: {suggestion.suggested_category ?? "(không đề xuất)"}</p>
            <p>Độ tin cậy: {Math.round(suggestion.confidence * 100)}%</p>
          </div>
          <label className="block">
            Caption do AI đề xuất (có thể sửa)
            <input
              className="mt-1 w-full rounded border border-amber-300 p-2 text-sm"
              value={caption}
              onChange={(event) => setCaption(event.target.value)}
            />
          </label>
          {suggestion.regions.length > 0 && (
            <p>{suggestion.regions.length} vùng ảnh cần xem xét.</p>
          )}
          <p className="whitespace-pre-wrap">{suggestion.disclaimer}</p>
          {suggestion.warnings.map((warning, index) => (
            <p key={`${index}-${warning}`}>{warning}</p>
          ))}
          <label className="flex items-start gap-2 font-medium">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            Tôi đã kiểm tra ảnh và xác nhận nội dung trước khi dùng làm chứng cứ.
          </label>
          {confirmed && (
            <p className="rounded bg-white p-2 text-[11px] text-gray-700">
              Đã xác nhận. Hãy lưu caption/loại ảnh trong module ảnh hiện trường; module
              này không tự động cập nhật SitePhoto.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
