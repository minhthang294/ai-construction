import { useEffect, useState } from "react";
import {
  ApiError,
  createManpowerPreset,
  deleteManpowerPreset,
  listManpowerPresets,
  ManpowerPresetInput,
  updateManpowerPreset,
} from "../lib/api";
import { parseManpowerCount } from "../lib/manpower";
import type { ManpowerPreset, Organization } from "../types";

type Props = {
  projectId: string;
  organizations: Organization[];
  onUse: (preset: ManpowerPreset) => void;
  onChanged?: (presets: ManpowerPreset[]) => void;
};

type Draft = {
  group_name: string;
  person_name: string;
  count_text: string;
  organization_id: string;
};

const EMPTY_DRAFT: Draft = {
  group_name: "",
  person_name: "",
  count_text: "",
  organization_id: "",
};

function draftFromPreset(preset: ManpowerPreset): Draft {
  return {
    group_name: preset.group_name,
    person_name: preset.person_name ?? "",
    count_text: preset.count === null ? "" : String(preset.count),
    organization_id: preset.organization_id ?? "",
  };
}

function toPayload(draft: Draft): ManpowerPresetInput {
  return {
    group_name: draft.group_name.trim(),
    person_name: draft.person_name.trim() || null,
    count: parseManpowerCount(draft.count_text),
    organization_id: draft.organization_id || null,
  };
}

function PresetFields({
  draft,
  organizations,
  onChange,
}: {
  draft: Draft;
  organizations: Organization[];
  onChange: (draft: Draft) => void;
}) {
  return (
    <div className="space-y-2">
      <input
        className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm"
        placeholder="Vai trò / nhóm (VD: Chỉ huy trưởng) *"
        value={draft.group_name}
        onChange={(event) => onChange({ ...draft, group_name: event.target.value })}
      />
      <input
        className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm"
        placeholder="Họ tên (tuỳ chọn)"
        value={draft.person_name}
        onChange={(event) => onChange({ ...draft, person_name: event.target.value })}
      />
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          inputMode="numeric"
          min={0}
          step={1}
          className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm"
          placeholder="Số lượng (trống = chưa rõ)"
          value={draft.count_text}
          onChange={(event) => onChange({ ...draft, count_text: event.target.value })}
        />
        <select
          className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={draft.organization_id}
          onChange={(event) =>
            onChange({ ...draft, organization_id: event.target.value })
          }
        >
          <option value="">Không gắn tổ chức</option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>
              {organization.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default function ManpowerPresets({
  projectId,
  organizations,
  onUse,
  onChanged,
}: Props) {
  const [presets, setPresets] = useState<ManpowerPreset[]>([]);
  const [createDraft, setCreateDraft] = useState<Draft>(EMPTY_DRAFT);
  const [editId, setEditId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Draft>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    try {
      const rows = await listManpowerPresets(projectId);
      setPresets(rows);
      onChanged?.(rows);
    } catch {
      setPresets([]);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function errorMessage(error: unknown): string {
    return error instanceof ApiError ? error.message : "Thao tác mẫu thất bại.";
  }

  async function handleCreate() {
    if (!createDraft.group_name.trim()) {
      setMessage("Nhập tên nhóm trước khi lưu mẫu.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const created = await createManpowerPreset(projectId, toPayload(createDraft));
      setPresets((current) => {
        const next = [...current, created];
        onChanged?.(next);
        return next;
      });
      setCreateDraft(EMPTY_DRAFT);
      setMessage("Đã lưu mẫu nhân lực.");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdate(presetId: string) {
    if (!editDraft.group_name.trim()) {
      setMessage("Nhập tên nhóm trước khi lưu mẫu.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const updated = await updateManpowerPreset(
        projectId,
        presetId,
        toPayload(editDraft),
      );
      setPresets((current) => {
        const next = current.map((item) => (item.id === presetId ? updated : item));
        onChanged?.(next);
        return next;
      });
      setEditId(null);
      setMessage("Đã cập nhật mẫu.");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(preset: ManpowerPreset) {
    if (!window.confirm(`Xoá mẫu “${preset.group_name}”?`)) return;
    setBusy(true);
    setMessage(null);
    try {
      await deleteManpowerPreset(projectId, preset.id);
      setPresets((current) => {
        const next = current.filter((item) => item.id !== preset.id);
        onChanged?.(next);
        return next;
      });
      setMessage("Đã xoá mẫu.");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function organizationName(id?: string | null): string {
    if (!id) return "Không gắn tổ chức";
    return organizations.find((item) => item.id === id)?.name ?? id;
  }

  return (
    <details className="rounded-xl bg-white p-3 shadow-sm">
      <summary className="min-h-11 cursor-pointer py-2 text-lg font-semibold">
        Danh bạ nhân lực ({presets.length})
      </summary>
      <p className="mt-1 text-xs text-gray-500">
        Tên Chỉ huy trưởng/Kỹ thuật được tự lưu vào danh bạ khi lưu báo cáo. Bấm
        “Dùng” để điền đúng vai trò; số 0 và “chưa rõ” của dòng cũ được giữ nguyên.
      </p>

      <div className="mt-3 space-y-3">
        {presets.map((preset) => (
          <div
            key={preset.id}
            className="rounded-lg border border-gray-200 p-2 text-sm"
          >
            {editId === preset.id ? (
              <div className="space-y-2">
                <PresetFields
                  draft={editDraft}
                  organizations={organizations}
                  onChange={setEditDraft}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="min-h-11 min-w-11 flex-1 rounded-lg bg-green-700 px-3 text-xs font-medium text-white disabled:opacity-50"
                    disabled={busy}
                    onClick={() => void handleUpdate(preset.id)}
                  >
                    Lưu mẫu
                  </button>
                  <button
                    type="button"
                    className="min-h-11 min-w-11 rounded-lg border border-gray-300 px-3 text-xs"
                    onClick={() => setEditId(null)}
                  >
                    Huỷ
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {preset.group_name}
                      {preset.person_name ? ` — ${preset.person_name}` : ""}
                    </p>
                    <p className="text-xs text-gray-500">
                      {preset.count === null ? "Chưa rõ số lượng" : `${preset.count} người`}
                      {" · "}
                      {organizationName(preset.organization_id)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="min-h-11 min-w-11 shrink-0 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white"
                    onClick={() => onUse(preset)}
                  >
                    Dùng
                  </button>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="min-h-11 min-w-11 rounded border border-gray-300 px-3 text-xs"
                    onClick={() => {
                      setEditId(preset.id);
                      setEditDraft(draftFromPreset(preset));
                    }}
                  >
                    Sửa
                  </button>
                  <button
                    type="button"
                    className="min-h-11 min-w-11 rounded border border-red-300 px-3 text-xs text-red-700"
                    disabled={busy}
                    onClick={() => void handleDelete(preset)}
                  >
                    Xoá
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
        {presets.length === 0 && (
          <p className="text-xs text-gray-500">Chưa có nhân lực trong danh bạ.</p>
        )}

        <div className="rounded-lg border border-dashed border-gray-300 p-2">
          <p className="mb-2 text-sm font-medium">Thêm mẫu mới</p>
          <PresetFields
            draft={createDraft}
            organizations={organizations}
            onChange={setCreateDraft}
          />
          <button
            type="button"
            className="mt-2 min-h-11 min-w-11 w-full rounded-lg bg-gray-800 px-3 text-xs font-medium text-white disabled:opacity-50"
            disabled={busy}
            onClick={() => void handleCreate()}
          >
            Lưu thành mẫu
          </button>
        </div>

        {message && <p className="text-xs text-gray-600">{message}</p>}
      </div>
    </details>
  );
}
