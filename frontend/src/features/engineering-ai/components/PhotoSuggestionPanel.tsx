import { useRef, useState } from "react";
import { suggestPhoto } from "../lib/api";
import {
  BADGE,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  HELP_TEXT,
  LABEL,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { AlertIcon, PhotoIcon, SpinnerIcon } from "./icons";
import type { PhotoSuggestion } from "../types";

type Props = {
  projectId: string;
};

export default function PhotoSuggestionPanel({ projectId }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
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
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div className="max-w-3xl">
        <h2 className={SECTION_TITLE}>Đề xuất ảnh hiện trường</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          AI chỉ đề xuất loại ảnh/caption/vùng cần xem. Không tự ghi vào hồ sơ, không
          suy đoán GPS, kích thước, khối lượng hay nghiệm thu.
        </p>
      </div>

      <div className="max-w-3xl space-y-2">
        <p className={LABEL}>Ảnh hiện trường</p>
        <input
          ref={inputRef}
          id="eai-photo-file"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className={cx(BUTTON_SECONDARY, "w-full sm:w-auto")}
          onClick={() => inputRef.current?.click()}
        >
          <PhotoIcon className="h-4 w-4" />
          {file ? "Chọn ảnh khác" : "Chọn ảnh hiện trường"}
        </button>
        <p className={HELP_TEXT}>JPEG, PNG hoặc WebP. Ảnh chỉ dùng để AI đề xuất.</p>
      </div>

      <div className="max-w-3xl space-y-4">
          {preview && (
          <figure className="overflow-hidden rounded-lg border border-slate-200 bg-slate-100 p-2">
            <img
              src={preview}
              alt={file ? `Ảnh xem trước: ${file.name}` : "Ảnh xem trước"}
              className="mx-auto block max-h-72 w-auto max-w-full rounded object-contain"
            />
            {file && (
              <figcaption className="mt-2 px-1 text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">
                {file.name}
              </figcaption>
            )}
          </figure>
        )}

        <button
          type="button"
          className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
          onClick={() => void suggest()}
          disabled={!file || busy}
        >
          {busy ? (
            <SpinnerIcon className="h-4 w-4" />
          ) : (
            <PhotoIcon className="h-4 w-4" />
          )}
          {busy ? "Đang phân tích..." : "Đề xuất bằng AI"}
        </button>

        {error && (
          <div role="alert" className={PANEL_ALERT}>
            {error}
          </div>
        )}

        {suggestion && (
          <div
            aria-live="polite"
            className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950"
          >
            <div className="flex flex-wrap items-center gap-2">
              <p className="flex items-center gap-2 font-semibold">
                <AlertIcon className="h-4 w-4 shrink-0" />
                Đề xuất chưa được xác nhận
              </p>
              <span className={cx(BADGE, "border border-amber-300 bg-white text-amber-900")}>
                Độ tin cậy {Math.round(suggestion.confidence * 100)}%
              </span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <p>Loại ảnh: {suggestion.suggested_category ?? "(không đề xuất)"}</p>
              <p>{suggestion.regions.length} vùng ảnh cần xem xét.</p>
            </div>
            <label className={LABEL} htmlFor="eai-photo-caption">
              Caption do AI đề xuất (có thể sửa)
              <input
                id="eai-photo-caption"
                className={FIELD}
                value={caption}
                onChange={(event) => setCaption(event.target.value)}
              />
            </label>
            <p className="whitespace-pre-wrap">{suggestion.disclaimer}</p>
            {suggestion.warnings.map((warning, index) => (
              <p key={`${index}-${warning}`} className="text-xs leading-5">
                {warning}
              </p>
            ))}
            <label className="flex min-h-11 items-start gap-2 rounded-lg bg-white/70 p-3 font-medium">
              <input
                type="checkbox"
                className="mt-0.5 h-5 w-5 shrink-0 rounded border-amber-300 accent-[#405e9b]"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              Tôi đã kiểm tra ảnh và xác nhận nội dung trước khi dùng làm chứng cứ.
            </label>
            {confirmed && (
              <p
                role="status"
                className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-900"
              >
                Đã xác nhận. Hãy lưu caption/loại ảnh trong module ảnh hiện trường; module
                này không tự động cập nhật SitePhoto.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
