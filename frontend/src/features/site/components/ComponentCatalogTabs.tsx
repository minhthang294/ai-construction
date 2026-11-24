import {
  COMPONENT_VIEWS,
  FOCUS_RING,
  nextViewIndex,
  type ComponentView,
} from "../lib/componentCatalogImport";

type Props = {
  view: ComponentView;
  tabId: string;
  onChange: (view: ComponentView) => void;
};

export default function ComponentCatalogTabs({ view, tabId, onChange }: Props) {
  return (
    <div
      className="app-tab-scroll gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm"
      role="tablist"
      aria-label="Tiến độ, danh mục, nhật ký và mặt bằng cấu kiện"
      onKeyDown={(event) => {
        const next = nextViewIndex(
          COMPONENT_VIEWS.findIndex((item) => item.id === view),
          event.key,
        );
        if (next < 0) return;
        event.preventDefault();
        onChange(COMPONENT_VIEWS[next].id);
        event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
      }}
    >
      {COMPONENT_VIEWS.map(({ id, label }) => (
        <button
          key={id}
          id={`${tabId}-${id}`}
          type="button"
          role="tab"
          aria-selected={view === id}
          aria-controls={`${tabId}-panel`}
          tabIndex={view === id ? 0 : -1}
          className={`min-h-11 shrink-0 whitespace-nowrap rounded-lg px-3 ${
            view === id ? "bg-slate-800 text-white shadow-sm" : "text-slate-700 hover:bg-slate-100"
          } ${FOCUS_RING}`}
          onClick={() => onChange(id)}
        >
          <span className="text-sm font-semibold">{label}</span>
        </button>
      ))}
    </div>
  );
}
