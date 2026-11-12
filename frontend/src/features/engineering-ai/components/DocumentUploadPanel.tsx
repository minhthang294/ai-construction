import { useRef, useState } from "react";
import { uploadDocument } from "../lib/api";
import {
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  HELP_TEXT,
  LABEL,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
  BUTTON_PRIMARY,
} from "../lib/ui";
import { SpinnerIcon, UploadIcon } from "./icons";
import type { SourceDocument } from "../types";

type Props = {
  projectId: string;
  onUploaded: (document: SourceDocument) => void;
};

const TYPES = [
  { value: "", label: "Tự nhận loại" },
  { value: "drawing", label: "Bản vẽ" },
  { value: "specification", label: "Thuyết minh KTKT" },
  { value: "technical_guideline", label: "Chỉ dẫn kỹ thuật" },
  { value: "construction_method", label: "Biện pháp thi công" },
  { value: "standard", label: "Tiêu chuẩn" },
  { value: "material_record", label: "Hồ sơ vật liệu" },
  { value: "test_record", label: "Hồ sơ thí nghiệm" },
  { value: "acceptance_record", label: "Hồ sơ nghiệm thu" },
  { value: "instruction", label: "Chỉ dẫn khác" },
  { value: "report", label: "Báo cáo" },
  { value: "other", label: "Khác" },
];

export default function DocumentUploadPanel({ projectId, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [type, setType] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    const selected = Array.from(files);
    let uploaded = 0;
    for (const file of selected) {
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        setError(`${file.name}: chỉ chấp nhận PDF.`);
        continue;
      }
      try {
        const document = await uploadDocument(projectId, file, type || undefined, changeNote || undefined);
        onUploaded(document);
        uploaded += 1;
      } catch (err) {
        setError(`${file.name}: ${err instanceof Error ? err.message : "Tải lên thất bại."}`);
      }
    }
    if (uploaded > 0) {
      setMessage(
        `${uploaded} hồ sơ đã tải lên. Hệ thống đang trích xuất/OCR từng trang; trạng thái sẽ tự cập nhật.`,
      );
    }
    if (inputRef.current) inputRef.current.value = "";
    setBusy(false);
  }

  return (
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div className="max-w-3xl">
        <h2 className={SECTION_TITLE}>Tải hồ sơ PDF</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          PDF được lưu private theo công trình. Hệ thống đọc text từng trang; trang scan
          được render và OCR. Không có nội dung nào được ghi vào DB ngoài metadata/text.
        </p>
      </div>

      <div className="max-w-3xl space-y-4">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <label className={LABEL}>
            Loại hồ sơ
            <select
              className={FIELD}
              value={type}
              onChange={(event) => setType(event.target.value)}
              disabled={busy}
            >
              {TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              multiple
              className="hidden"
              onChange={(event) => handleFiles(event.target.files)}
            />
            <button
              type="button"
              className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
              onClick={() => inputRef.current?.click()}
              disabled={busy}
              aria-busy={busy}
            >
              {busy ? (
                <SpinnerIcon className="h-4 w-4" />
              ) : (
                <UploadIcon className="h-4 w-4" />
              )}
              {busy ? "Đang tải..." : "Chọn PDF"}
            </button>
          </div>
        </div>

        <label className={LABEL}>
          Mô tả thay đổi (tuỳ chọn, dùng khi tải revision)
          <input
            className={FIELD}
            value={changeNote}
            maxLength={2000}
            placeholder="Ví dụ: Rev B - cập nhật cao độ neo"
            aria-describedby="eai-change-note-help"
            onChange={(event) => setChangeNote(event.target.value)}
            disabled={busy}
          />
          <span id="eai-change-note-help" className={cx(HELP_TEXT, "flex justify-between gap-2")}>
            <span>Giúp kỹ sư phân biệt các lần phát hành.</span>
            <span className="shrink-0 tabular-nums">{changeNote.length}/2000</span>
          </span>
        </label>

        {message && (
          <div
            role="status"
            className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-900"
          >
            {message}
          </div>
        )}
        {error && (
          <div role="alert" className={PANEL_ALERT}>
            {error}
          </div>
        )}
      </div>
    </section>
  );
}
