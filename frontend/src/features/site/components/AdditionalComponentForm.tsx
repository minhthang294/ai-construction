import { useEffect, useMemo, useState } from "react";
import { ApiError, addConstructionBatchComponents, createComponent, listComponents, listDesignGroups } from "../lib/api";
import type {
  ComponentSegment,
  ComponentSummary,
  ComponentType,
  DesignGroupSummary,
} from "../lib/componentImport";

type Props = {
  projectId: string;
  batchId: string | null;
  segments: ComponentSegment[];
  primaryZone: string | null;
  onCreated: (component: ComponentSummary) => void;
};

type Draft = {
  segment_id: string;
  type: ComponentType | "";
  canonical_code: string;
  raw_code: string;
  design_group_id: string;
  approval_reference: string;
  add_to_batch: boolean;
};

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-700 focus-visible:ring-offset-2";
const FIELD_CLASS = `min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-slate-500 ${FOCUS_RING}`;
const PRIMARY_BUTTON = `min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`;
const SECONDARY_BUTTON = `min-h-11 rounded-lg border border-gray-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-gray-100 ${FOCUS_RING}`;
const DETAILS_SUMMARY = `flex min-h-11 cursor-pointer flex-wrap items-center justify-between gap-2 px-3 py-2 text-left ${FOCUS_RING}`;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

function initialDraft(
  segments: ComponentSegment[],
  primaryZone: string | null,
  batchId: string | null,
): Draft {
  const preferred =
    segments.find((segment) => segment.zone === primaryZone) ?? segments[0];
  return {
    segment_id: preferred?.id ?? "",
    type: "",
    canonical_code: "",
    raw_code: "",
    design_group_id: "",
    approval_reference: "",
    add_to_batch: Boolean(batchId),
  };
}

export default function AdditionalComponentForm({
  projectId,
  batchId,
  segments,
  primaryZone,
  onCreated,
}: Props) {
  const [draft, setDraft] = useState<Draft>(() =>
    initialDraft(segments, primaryZone, batchId),
  );
  const [groups, setGroups] = useState<DesignGroupSummary[]>([]);
  const [duplicates, setDuplicates] = useState<ComponentSummary[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [batchWarning, setBatchWarning] = useState<string | null>(null);

  useEffect(() => {
    setDraft(initialDraft(segments, primaryZone, batchId));
  }, [segments, primaryZone, batchId]);

  useEffect(() => {
    listDesignGroups(projectId)
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [projectId]);

  const zoneSegments = useMemo(
    () =>
      primaryZone
        ? segments.filter((segment) => segment.zone === primaryZone)
        : segments,
    [segments, primaryZone],
  );

  function patch(next: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...next }));
    setDuplicates(null);
    setError(null);
    setMessage(null);
  }

  async function findDuplicates(): Promise<ComponentSummary[]> {
    const canonical = draft.canonical_code.trim().toUpperCase();
    const raw = (draft.raw_code.trim() || canonical).toUpperCase();
    const queries = Array.from(new Set([canonical, raw].filter(Boolean)));
    const found = new Map<string, ComponentSummary>();
    for (const query of queries) {
      for (const row of await listComponents(projectId, query)) {
        if (
          row.segment_id === draft.segment_id &&
          row.type === draft.type
        ) {
          found.set(row.id, row);
        }
      }
    }
    return Array.from(found.values());
  }

  async function handleCheck() {
    if (!draft.canonical_code.trim() || !draft.segment_id || !draft.type) {
      setError("Chọn phân đoạn, loại và nhập mã cấu kiện trước khi kiểm tra.");
      return;
    }
    setChecking(true);
    setError(null);
    try {
      setDuplicates(await findDuplicates());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setChecking(false);
    }
  }

  async function handleSubmit() {
    const canonical = draft.canonical_code.trim();
    const raw = draft.raw_code.trim() || canonical;
    if (!draft.segment_id) {
      setError("Chọn phân đoạn.");
      return;
    }
    if (!draft.type) {
      setError("Chọn loại cấu kiện.");
      return;
    }
    if (!canonical) {
      setError("Nhập mã cấu kiện.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    setBatchWarning(null);
    try {
      const existing = await findDuplicates();
      if (existing.length) {
        setDuplicates(existing);
        setError("Mã đã có trong phân đoạn này. Kiểm tra lại trước khi tạo.");
        return;
      }
      const created = await createComponent(projectId, {
        segment_id: draft.segment_id,
        type: draft.type,
        raw_code: raw,
        canonical_code: canonical,
        scope: "ADDITIONAL_SCOPE",
        design_group_id: draft.design_group_id || null,
        approval_reference: draft.approval_reference.trim() || null,
      });
      setMessage(
        `Đã tạo cấu kiện phát sinh ${created.canonical_code}. Chạm lên bản vẽ để đặt vị trí.`,
      );
      setDraft((current) => ({
        ...current,
        canonical_code: "",
        raw_code: "",
        approval_reference: "",
      }));
      setDuplicates(null);
      if (batchId && draft.add_to_batch) {
        try {
          await addConstructionBatchComponents(
            projectId,
            batchId,
            [created.id],
            "Cấu kiện phát sinh thêm vào đợt",
          );
        } catch (err) {
          setBatchWarning(
            `Đã tạo cấu kiện nhưng chưa thêm được vào đợt: ${errorMessage(err)}`,
          );
        }
      }
      onCreated(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <summary className={DETAILS_SUMMARY}>
        <span className="text-base font-semibold text-slate-900">
          Thêm cấu kiện phát sinh
        </span>
        <span className="text-xs font-normal text-slate-600">
          Tạo mới và đặt vị trí trên bản vẽ
        </span>
      </summary>
      <div className="border-t border-gray-100 p-3">
        <p className="text-xs leading-5 text-slate-600">
          Cấu kiện được ghi ở phạm vi phát sinh, chờ duyệt danh mục. Vị trí lưu
          dạng nháp để quản lý dự án duyệt lại.
        </p>
        <form
          className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
        >
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Khu / phân đoạn
            <select
              className={FIELD_CLASS}
              value={draft.segment_id}
              disabled={busy || zoneSegments.length === 0}
              onChange={(event) => patch({ segment_id: event.target.value })}
            >
              <option value="">Chọn phân đoạn</option>
              {zoneSegments.map((segment) => (
                <option key={segment.id} value={segment.id}>
                  {segment.zone} · PĐ {segment.number}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-0 text-xs font-medium text-slate-700">
            Loại cấu kiện
            <select
              className={FIELD_CLASS}
              value={draft.type}
              disabled={busy}
              onChange={(event) =>
                patch({ type: event.target.value as ComponentType | "" })
              }
            >
              <option value="">Chọn loại</option>
              <option value="pile">Cọc</option>
              <option value="beam">Dầm</option>
            </select>
          </label>

          <label className="min-w-0 text-xs font-medium text-slate-700">
            Mã cấu kiện
            <input
              className={FIELD_CLASS}
              value={draft.canonical_code}
              maxLength={120}
              disabled={busy}
              placeholder="Ví dụ F-24-25"
              onChange={(event) => patch({ canonical_code: event.target.value })}
            />
          </label>

          <label className="min-w-0 text-xs font-medium text-slate-700">
            Mã gốc trên hồ sơ
            <input
              className={FIELD_CLASS}
              value={draft.raw_code}
              maxLength={120}
              disabled={busy}
              placeholder="Để trống nếu trùng mã cấu kiện"
              onChange={(event) => patch({ raw_code: event.target.value })}
            />
          </label>

          <label className="min-w-0 text-xs font-medium text-slate-700">
            Nhóm thiết kế (tùy chọn)
            <select
              className={FIELD_CLASS}
              value={draft.design_group_id}
              disabled={busy}
              onChange={(event) => patch({ design_group_id: event.target.value })}
            >
              <option value="">Không gán nhóm</option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                  {group.drawing ? ` · ${group.drawing}` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-0 text-xs font-medium text-slate-700">
            Căn cứ / hồ sơ phát sinh (tùy chọn)
            <input
              className={FIELD_CLASS}
              value={draft.approval_reference}
              maxLength={1000}
              disabled={busy}
              placeholder="Số văn bản, biên bản hiện trường…"
              onChange={(event) =>
                patch({ approval_reference: event.target.value })
              }
            />
          </label>

          {batchId ? (
            <label className="flex min-h-11 items-center gap-2 text-sm text-slate-800 sm:col-span-2">
              <input
                type="checkbox"
                className="h-5 w-5 rounded border-gray-300"
                checked={draft.add_to_batch}
                disabled={busy}
                onChange={(event) => patch({ add_to_batch: event.target.checked })}
              />
              Thêm vào đợt đang chọn
            </label>
          ) : null}

          {duplicates?.length ? (
            <div
              role="status"
              className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950 sm:col-span-2"
            >
              <p className="font-semibold">Mã đã tồn tại trong phân đoạn:</p>
              <ul className="mt-1 space-y-0.5">
                {duplicates.slice(0, 5).map((row) => (
                  <li key={row.id} className="break-all font-mono">
                    {row.canonical_code} · {row.type === "pile" ? "Cọc" : "Dầm"}
                  </li>
                ))}
              </ul>
            </div>
          ) : duplicates ? (
            <p
              role="status"
              className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900 sm:col-span-2"
            >
              Chưa thấy mã trùng trong phân đoạn này.
            </p>
          ) : null}

          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-900 sm:col-span-2"
            >
              {error}
            </p>
          ) : null}

          {message ? (
            <p
              role="status"
              className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900 sm:col-span-2"
            >
              {message}
            </p>
          ) : null}

          {batchWarning ? (
            <p
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950 sm:col-span-2"
            >
              {batchWarning}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <button
              type="submit"
              className={`${PRIMARY_BUTTON} flex-1`}
              disabled={busy || segments.length === 0}
            >
              {busy ? "Đang tạo cấu kiện…" : "Tạo và đặt vị trí"}
            </button>
            <button
              type="button"
              className={SECONDARY_BUTTON}
              disabled={busy || checking}
              onClick={() => void handleCheck()}
            >
              {checking ? "Đang kiểm tra…" : "Kiểm tra trùng"}
            </button>
          </div>
        </form>
      </div>
    </details>
  );
}
