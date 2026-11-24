import type { ComponentCandidate } from "../lib/componentImport";
import {
  componentScopeLabel,
  componentTypeLabel,
} from "../lib/componentCatalogImport";

export default function CatalogCandidateCard({
  component,
}: {
  component: ComponentCandidate;
}) {
  return (
    <article className="rounded-xl border border-gray-200 bg-white p-3 text-sm shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="break-all font-mono text-base font-semibold text-slate-900">
            {component.canonical_code}
          </p>
          {component.raw_code !== component.canonical_code ? (
            <p className="font-mono text-xs text-amber-700">
              Mã gốc: {component.raw_code}
            </p>
          ) : null}
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
          dòng {component.source_row}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-slate-600">Mã nguồn</dt>
          <dd className="break-all font-mono">{component.source_id}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Khu / phân đoạn</dt>
          <dd>
            {component.zone} · PĐ {component.segment}
          </dd>
        </div>
        <div>
          <dt className="text-slate-600">Loại</dt>
          <dd>{componentTypeLabel(component.type)}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Phạm vi</dt>
          <dd>{componentScopeLabel(component.scope)}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Nhóm thiết kế</dt>
          <dd>{component.design_group ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Bản vẽ</dt>
          <dd>{component.drawing || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Nguồn</dt>
          <dd>{component.source || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Xác minh danh mục</dt>
          <dd>Chờ duyệt</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-600">Tên khác</dt>
          <dd className="break-all font-mono">
            {component.aliases.length ? component.aliases.join(", ") : "—"}
          </dd>
        </div>
      </dl>
    </article>
  );
}
