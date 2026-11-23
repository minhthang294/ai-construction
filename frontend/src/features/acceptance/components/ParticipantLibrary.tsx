import { useEffect, useState } from "react";
import {
  createParticipantProfile,
  deleteParticipantProfile,
  listParticipantProfiles,
  updateParticipantProfile,
} from "../lib/api";
import type { ParticipantProfile, ParticipantProfileInput, ParticipantRole } from "../types";

type Props = {
  projectId: string;
  onChanged?: (profiles: ParticipantProfile[]) => void;
};

const ROLE_OPTIONS: ReadonlyArray<{ value: ParticipantRole; label: string }> = [
  { value: "requester", label: "Người yêu cầu" },
  { value: "supervisor", label: "Tư vấn giám sát" },
  { value: "investor", label: "Chủ đầu tư" },
  { value: "contractor", label: "Nhà thầu" },
  { value: "other", label: "Khác" },
];

const EMPTY: ParticipantProfileInput = {
  full_name: "",
  organization: "",
  position: "",
  role: "requester",
  active: true,
};

export default function ParticipantLibrary({ projectId, onChanged }: Props) {
  const [profiles, setProfiles] = useState<ParticipantProfile[]>([]);
  const [form, setForm] = useState<ParticipantProfileInput>({ ...EMPTY });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const rows = await listParticipantProfiles(projectId);
    setProfiles(rows);
    onChanged?.(rows);
  }

  useEffect(() => {
    refresh().catch((cause) =>
      setError(cause instanceof Error ? cause.message : "Không tải được danh bạ."),
    );
  }, [projectId]);

  async function addProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!form.full_name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createParticipantProfile(projectId, { ...form, full_name: form.full_name.trim() });
      setForm({ ...EMPTY });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thêm được người tham gia.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(profile: ParticipantProfile) {
    setBusy(true);
    setError(null);
    try {
      await updateParticipantProfile(projectId, profile.id, { active: !profile.active });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không cập nhật được.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(profile: ParticipantProfile) {
    setBusy(true);
    setError(null);
    try {
      await deleteParticipantProfile(projectId, profile.id);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không xóa được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm">
      <h2 className="font-semibold">Danh bạ người tham gia</h2>
      <p className="mb-2 text-sm text-slate-500">
        Chọn từ danh bạ khi lập PYC. Hệ thống chỉ lưu snapshot họ tên/đơn vị, không tự tạo chữ ký.
      </p>

      <ul className="divide-y">
        {profiles.map((profile) => (
          <li key={profile.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
            <span className="min-w-0 flex-1">
              <strong>{profile.full_name}</strong> — {profile.position || "—"} —{" "}
              {profile.organization || "—"}{" "}
              <span className="text-sm text-slate-600">
                ({ROLE_OPTIONS.find((option) => option.value === profile.role)?.label ?? profile.role})
              </span>
              {!profile.active && <span className="ml-1 text-rose-700">[ngừng]</span>}
            </span>
            <button
              type="button"
              onClick={() => toggleActive(profile)}
              disabled={busy}
              className="min-h-11 rounded border px-3 py-2 text-sm"
            >
              {profile.active ? "Ngừng" : "Kích hoạt"}
            </button>
            <button
              type="button"
              onClick={() => remove(profile)}
              disabled={busy}
              className="min-h-11 rounded border border-rose-300 px-3 py-2 text-sm text-rose-700"
            >
              Xóa
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={addProfile} className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="block text-sm">
          Họ tên
          <input
            className="mt-1 min-h-11 w-full rounded border p-2"
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
            required
          />
        </label>
        <label className="block text-sm">
          Vai trò
          <select
            className="mt-1 min-h-11 w-full rounded border p-2"
            value={form.role}
            onChange={(event) =>
              setForm({ ...form, role: event.target.value as ParticipantRole })
            }
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Đơn vị
          <input
            className="mt-1 min-h-11 w-full rounded border p-2"
            value={form.organization ?? ""}
            onChange={(event) => setForm({ ...form, organization: event.target.value })}
          />
        </label>
        <label className="block text-sm">
          Chức vụ
          <input
            className="mt-1 min-h-11 w-full rounded border p-2"
            value={form.position ?? ""}
            onChange={(event) => setForm({ ...form, position: event.target.value })}
          />
        </label>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-teal-700 px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            + Thêm vào danh bạ
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="mt-2 rounded bg-rose-50 p-2 text-sm text-rose-800">
          {error}
        </p>
      )}
    </section>
  );
}


