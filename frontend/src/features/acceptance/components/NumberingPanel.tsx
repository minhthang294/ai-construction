import { useEffect, useState } from "react";
import { listNumbering, updateNumbering } from "../lib/api";
import type { NumberingConfig, ResetPolicy } from "../types";

type Props = {
  projectId: string;
  onSaved?: (config: NumberingConfig) => void;
};

type Form = {
  kind: "pyc" | "bbnt";
  prefix: string;
  start_number: number;
  width: number;
  reset_policy: ResetPolicy;
  date_format: string;
};

const DEFAULTS: Form = {
  kind: "pyc",
  prefix: "PYC-",
  start_number: 1,
  width: 3,
  reset_policy: "never",
  date_format: "%Y",
};

export default function NumberingPanel({ projectId, onSaved }: Props) {
  const [configs, setConfigs] = useState<NumberingConfig[]>([]);
  const [form, setForm] = useState<Form>({ ...DEFAULTS });
  const [nextNumber, setNextNumber] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function applyConfig(kind: "pyc" | "bbnt", rows: NumberingConfig[]) {
    const found = rows.find((row) => row.kind === kind);
    if (found) {
      setForm({
        kind,
        prefix: found.prefix,
        start_number: found.start_number,
        width: found.width,
        reset_policy: found.reset_policy,
        date_format: found.date_format,
      });
      setNextNumber(found.next_number);
    } else {
      setForm({
        ...DEFAULTS,
        kind,
        prefix: kind === "pyc" ? "PYC-" : "BBNT-",
      });
      setNextNumber(1);
    }
  }

  async function refresh(kind = form.kind) {
    const rows = await listNumbering(projectId);
    setConfigs(rows);
    applyConfig(kind, rows);
  }

  useEffect(() => {
    refresh("pyc").catch((cause) =>
      setError(cause instanceof Error ? cause.message : "Không tải được cấu hình số."),
    );
  }, [projectId]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await updateNumbering(projectId, form.kind, {
        prefix: form.prefix,
        start_number: form.start_number,
        width: form.width,
        reset_policy: form.reset_policy,
        date_format: form.date_format,
      });
      const rows = await listNumbering(projectId);
      setConfigs(rows);
      applyConfig(form.kind, rows);
      setMessage(`Đã lưu cấu hình ${form.kind.toUpperCase()}.`);
      onSaved?.(saved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không lưu được cấu hình số.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm" aria-label="Cấu hình số nghiệm thu">
      <h2 className="font-semibold">Cấu hình số PYC/BBNT</h2>
      <p className="mb-2 text-xs text-slate-500">
        Số được cấp nguyên tử phía máy chủ; lưu cấu hình sẽ đặt lại next number về số bắt đầu.
      </p>

      <form onSubmit={save} className="space-y-2">
        <label className="block text-sm">
          Loại phiếu
          <select
            className="mt-1 w-full rounded border p-2"
            value={form.kind}
            onChange={(event) => {
              const kind = event.target.value as "pyc" | "bbnt";
              setForm({ ...form, kind });
              applyConfig(kind, configs);
            }}
          >
            <option value="pyc">PYC — Phiếu yêu cầu</option>
            <option value="bbnt">BBNT — Biên bản nghiệm thu</option>
          </select>
        </label>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            Prefix
            <input
              className="mt-1 w-full rounded border p-2"
              value={form.prefix}
              onChange={(event) => setForm({ ...form, prefix: event.target.value })}
            />
          </label>
          <label className="block text-sm">
            Bắt đầu
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded border p-2"
              value={form.start_number}
              onChange={(event) =>
                setForm({ ...form, start_number: Number(event.target.value) || 1 })
              }
            />
          </label>
          <label className="block text-sm">
            Độ rộng số
            <input
              type="number"
              min={1}
              max={10}
              className="mt-1 w-full rounded border p-2"
              value={form.width}
              onChange={(event) =>
                setForm({ ...form, width: Number(event.target.value) || 1 })
              }
            />
          </label>
          <label className="block text-sm">
            Date format
            <input
              className="mt-1 w-full rounded border p-2"
              value={form.date_format}
              onChange={(event) => setForm({ ...form, date_format: event.target.value })}
            />
          </label>
        </div>

        <label className="block text-sm">
          Reset policy
          <select
            className="mt-1 w-full rounded border p-2"
            value={form.reset_policy}
            onChange={(event) =>
              setForm({ ...form, reset_policy: event.target.value as ResetPolicy })
            }
          >
            <option value="never">never — không đánh lại</option>
            <option value="yearly">yearly — theo năm</option>
            <option value="monthly">monthly — theo tháng</option>
          </select>
        </label>

        <p className="text-sm text-slate-600">
          Next number: <strong>{nextNumber ?? "—"}</strong>
        </p>

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-teal-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Đang lưu..." : "Lưu cấu hình số"}
        </button>
      </form>

      {message && <p className="mt-2 rounded bg-emerald-50 p-2 text-sm text-emerald-900">{message}</p>}
      {error && (
        <p role="alert" className="mt-2 rounded bg-rose-50 p-2 text-sm text-rose-800">
          {error}
        </p>
      )}
    </section>
  );
}
