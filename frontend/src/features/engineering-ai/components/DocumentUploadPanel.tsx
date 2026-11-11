import { useRef, useState } from "react";
import { uploadDocument } from "../lib/api";
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
    <section className="rounded border border-gray-200 bg-white p-3 shadow-sm space-y-3">
      <div>
        <h2 className="text-sm font-semibold">Tải hồ sơ PDF</h2>
        <p className="text-xs text-gray-600">
          PDF được lưu private theo công trình. Hệ thống đọc text từng trang; trang scan
          được render và OCR. Không có nội dung nào được ghi vào DB ngoài metadata/text.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
        <label className="text-xs font-medium text-gray-700">
          Loại hồ sơ
          <select
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
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
        <div className="flex items-end">
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
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 sm:w-auto"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? "Đang tải..." : "Chọn PDF"}
          </button>
        </div>
      </div>

      <label className="block text-xs font-medium text-gray-700">
        Mô tả thay đổi (tuỳ chọn, dùng khi tải revision)
        <input
          className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
          value={changeNote}
          maxLength={2000}
          placeholder="Ví dụ: Rev B - cập nhật cao độ neo"
          onChange={(event) => setChangeNote(event.target.value)}
          disabled={busy}
        />
      </label>

      {message && (
        <div className="rounded bg-green-50 p-2 text-xs text-green-800">{message}</div>
      )}
      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}
    </section>
  );
}
