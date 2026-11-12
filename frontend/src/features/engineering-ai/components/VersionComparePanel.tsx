import { useEffect, useState } from "react";
import { compareVersions, listVersions } from "../lib/api";
import {
  BUTTON_PRIMARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD_INLINE,
  LABEL,
  META_TEXT,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { CompareIcon, SpinnerIcon } from "./icons";
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
      <section className={cx(CARD, CARD_PAD, "flex gap-3")}>
        <CompareIcon className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
        <p className={SECTION_TEXT}>Hồ sơ này chưa có từ hai phiên bản để so sánh.</p>
      </section>
    );
  }

  return (
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div>
        <h2 className={SECTION_TITLE}>Phiên bản & hiệu lực</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          So sánh metadata/thống kê trang/chunk. Không kết luận thay đổi thiết kế.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[
          ["Bản trái", leftId, setLeftId],
          ["Bản phải", rightId, setRightId],
        ].map(([label, value, setter]) => (
          <label key={String(label)} className={LABEL}>
            {String(label)}
            <select
              className={cx(FIELD_INLINE, "mt-1.5 w-full")}
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
        className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
        onClick={() => void compare()}
        disabled={busy || leftId === rightId}
      >
        {busy && <SpinnerIcon className="h-4 w-4" />}
        {busy ? "Đang so sánh..." : "So sánh hai phiên bản"}
      </button>

      {error && (
        <div role="alert" className={PANEL_ALERT}>
          {error}
        </div>
      )}

      {result && (
        <div aria-live="polite" className="space-y-3">
          <div className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="font-semibold text-slate-900">v{result.left.version}</p>
              <p className={META_TEXT}>
                {result.left.page_count} trang · {result.left.chunk_count} chunk
              </p>
              <p className={META_TEXT}>
                {result.left.total_chars} ký tự · {result.left_table_count} bảng
              </p>
              <p className={META_TEXT}>
                {result.left.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="font-semibold text-slate-900">v{result.right.version}</p>
              <p className={META_TEXT}>
                {result.right.page_count} trang · {result.right.chunk_count} chunk
              </p>
              <p className={META_TEXT}>
                {result.right.total_chars} ký tự · {result.right_table_count} bảng
              </p>
              <p className={META_TEXT}>
                {result.right.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}
              </p>
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-700 tabular-nums">
            Δ trang: {result.page_count_delta} · Δ chunk: {result.chunk_count_delta} · Δ ký tự:{" "}
            {result.total_chars_delta}
          </p>
          <p className={SECTION_TEXT}>
            {result.page_changes.filter((page) => page.changed).length} trang có khác biệt
            số ký tự. {result.disclaimer}
          </p>
        </div>
      )}
    </section>
  );
}
