import { useEffect, useState } from "react";
import { compareVersions, listVersions } from "../lib/api";
import type { SourceDocument, VersionCompareResponse } from "../types";

type Props = {
  projectId: string;
  document: SourceDocument;
};

export default function VersionComparePanel({ projectId, document }: Props) {
  const [versions, setVersions] = useState<SourceDocument[]>([]);
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [result, setResult] = useState<VersionCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const items = await listVersions(projectId, document.id);
        if (cancelled) return;
        setVersions(items);
        setLeftId((current) => current || items[0]?.id || "");
        setRightId((current) => current || items[1]?.id || items[0]?.id || "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Không tải được phiên bản.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, document.id]);

  async function compare() {
    if (!leftId || !rightId || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await compareVersions(projectId, leftId, rightId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không so sánh được phiên bản.");
    } finally {
      setBusy(false);
    }
  }

  if (versions.length < 2) {
    return (
      <section className="rounded border border-gray-200 bg-white p-3 text-xs text-gray-600 shadow-sm">
        Hồ sơ này chưa có từ hai phiên bản để so sánh.
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded border border-gray-200 bg-white p-3 shadow-sm">
      <div>
        <h2 className="text-sm font-semibold">Phiên bản & hiệu lực</h2>
        <p className="text-xs text-gray-600">
          So sánh metadata/thống kê trang/chunk. Không kết luận thay đổi thiết kế.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {[
          ["Bản trái", leftId, setLeftId],
          ["Bản phải", rightId, setRightId],
        ].map(([label, value, setter]) => (
          <label key={String(label)} className="block text-xs font-medium text-gray-700">
            {String(label)}
            <select
              className="mt-1 w-full rounded border border-gray-300 p-2 text-xs"
              value={String(value)}
              onChange={(event) => (setter as (v: string) => void)(event.target.value)}
            >
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version} · {version.is_effective ? "hiệu lực" : "chưa hiệu lực"}
                  {version.is_current ? " · mới nhất" : ""}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <button
        type="button"
        className="rounded bg-gray-800 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
        onClick={() => void compare()}
        disabled={busy || leftId === rightId}
      >
        {busy ? "Đang so sánh..." : "So sánh hai phiên bản"}
      </button>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {result && (
        <div className="space-y-2">
          <div className="grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded bg-gray-50 p-2">
              <p className="font-semibold">v{result.left.version}</p>
              <p>{result.left.page_count} trang · {result.left.chunk_count} chunk</p>
              <p>{result.left.total_chars} ký tự · {result.left_table_count} bảng</p>
              <p>{result.left.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <p className="font-semibold">v{result.right.version}</p>
              <p>{result.right.page_count} trang · {result.right.chunk_count} chunk</p>
              <p>{result.right.total_chars} ký tự · {result.right_table_count} bảng</p>
              <p>{result.right.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}</p>
            </div>
          </div>
          <p className="text-xs">
            Δ trang: {result.page_count_delta} · Δ chunk: {result.chunk_count_delta} · Δ ký tự:{" "}
            {result.total_chars_delta}
          </p>
          <p className="text-xs text-gray-600">
            {result.page_changes.filter((page) => page.changed).length} trang có khác biệt
            số ký tự. {result.disclaimer}
          </p>
        </div>
      )}
    </section>
  );
}
