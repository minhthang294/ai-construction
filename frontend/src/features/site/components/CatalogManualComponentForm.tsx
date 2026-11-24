import type {
  ComponentSegment,
  ManualComponentDraft,
} from "../lib/componentImport";
import {
  DETAILS_SUMMARY,
  FIELD_CLASS,
  PRIMARY_BUTTON,
  segmentLabel,
} from "../lib/componentCatalogImport";

type Props = {
  manual: ManualComponentDraft;
  segments: ComponentSegment[];
  manualBusy: boolean;
  manualError: string | null;
  manualMessage: string | null;
  onChange: (patch: Partial<ManualComponentDraft>) => void;
  onSubmit: () => void;
};

export default function CatalogManualComponentForm({
  manual,
  segments,
  manualBusy,
  manualError,
  manualMessage,
  onChange,
  onSubmit,
}: Props) {
  return (
    <details className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <summary className={DETAILS_SUMMARY}>
        <span className="text-base font-semibold text-slate-900">
          Tạo cấu kiện thủ công
        </span>
        <span className="text-xs font-normal text-slate-600">
          Chỉ dùng phân đoạn đã có
        </span>
      </summary>
      <div className="border-t border-gray-100 p-3">
        <p className="text-xs text-slate-600">
          UI không tạo nguồn, bản vẽ hay nghiệm thu; máy chủ gán trạng thái
          xác minh.
        </p>
        <form
          className="mt-3 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="text-xs font-semibold text-slate-700">
              Phân đoạn
              <select
                required
                className={`${FIELD_CLASS} mt-1`}
                value={manual.segment_id}
                disabled={manualBusy || segments.length === 0}
                onChange={(event) => onChange({ segment_id: event.target.value })}
              >
                <option value="">— Chọn phân đoạn đã có —</option>
                {segments.map((segment) => (
                  <option key={segment.id} value={segment.id}>
                    {segmentLabel(segment)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Loại
              <select
                required
                className={`${FIELD_CLASS} mt-1`}
                value={manual.type}
                disabled={manualBusy}
                onChange={(event) =>
                  onChange({
                    type: event.target.value as ManualComponentDraft["type"],
                  })
                }
              >
                <option value="">— Chọn loại —</option>
                <option value="pile">Cọc (pile)</option>
                <option value="beam">Dầm (beam)</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Mã gốc (raw_code)
              <input
                required
                maxLength={120}
                className={`${FIELD_CLASS} mt-1`}
                value={manual.raw_code}
                disabled={manualBusy}
                placeholder="Ví dụ I40-42"
                onChange={(event) => onChange({ raw_code: event.target.value })}
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Mã chuẩn (canonical_code)
              <input
                required
                maxLength={120}
                className={`${FIELD_CLASS} mt-1`}
                value={manual.canonical_code}
                disabled={manualBusy}
                placeholder="Ví dụ I-40-42"
                onChange={(event) =>
                  onChange({ canonical_code: event.target.value })
                }
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Phạm vi
              <select
                required
                className={`${FIELD_CLASS} mt-1`}
                value={manual.scope}
                disabled={manualBusy}
                onChange={(event) =>
                  onChange({
                    scope: event.target.value as ManualComponentDraft["scope"],
                  })
                }
              >
                <option value="">— Chọn phạm vi —</option>
                <option value="DESIGN_SCOPE">Theo thiết kế</option>
                <option value="ADDITIONAL_SCOPE">
                  Phát sinh sửa chữa
                </option>
              </select>
            </label>
          </div>

          {segments.length === 0 ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950">
              Chưa có phân đoạn trong công trình. Nhập workbook có phân đoạn
              trước khi tạo cấu kiện thủ công.
            </p>
          ) : null}
          {manualError ? (
            <p
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-800"
            >
              {manualError}
            </p>
          ) : null}
          {manualMessage ? (
            <p
              role="status"
              className="rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-800"
            >
              {manualMessage}
            </p>
          ) : null}
          <button
            type="submit"
            className={`${PRIMARY_BUTTON} w-full`}
            disabled={manualBusy || segments.length === 0}
          >
            {manualBusy ? "Đang tạo cấu kiện…" : "Tạo cấu kiện"}
          </button>
        </form>
      </div>
    </details>
  );
}
