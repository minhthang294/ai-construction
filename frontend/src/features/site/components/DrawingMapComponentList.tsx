/** Sheet-by-sheet component list under the drawing map. */

import {
  componentTypeLabel,
  constructionStatusLabel,
  originLabel,
  type DrawingMarker,
  type DrawingSheet,
} from "../lib/drawingMap";
import { FOCUS_RING } from "../lib/drawingMapPanel";

type Props = {
  filteredSheets: ReadonlyArray<DrawingSheet>;
  visibleMarkerCount: number;
  openDetail: (marker: DrawingMarker) => void;
};

export default function DrawingMapComponentList({
  filteredSheets,
  visibleMarkerCount,
  openDetail,
}: Props) {
  return (
    <details
      className="rounded-xl border border-slate-200 bg-white shadow-sm"
      open
    >
      <summary
        className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 p-3 text-sm font-semibold text-slate-900 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
      >
        <span>Danh sách cấu kiện ({visibleMarkerCount})</span>
        <span aria-hidden="true" className="text-slate-500">
          ⌄
        </span>
      </summary>
      <div className="divide-y divide-slate-200 border-t border-slate-200">
        {filteredSheets.map((sheet) => (
          <section key={sheet.id} className="p-3">
            <h5 className="break-words text-sm font-semibold text-slate-900">
              {sheet.title}
            </h5>
            <p className="mt-0.5 text-xs text-slate-600">
              Bản vẽ {sheet.drawing} · trang {sheet.page}
            </p>
            {sheet.markers.length ? (
              <ul className="mt-2 space-y-1">
                {sheet.markers.map((marker) => (
                  <li
                    key={`${marker.component_id}-${marker.code}`}
                  >
                    <button
                      type="button"
                      className={`flex min-h-11 w-full min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-200 px-2 py-1 text-left text-sm text-slate-800 active:bg-slate-50 ${FOCUS_RING}`}
                      onClick={() => void openDetail(marker)}
                    >
                      <span className="break-words font-mono font-semibold text-slate-900">
                        {marker.code}
                      </span>
                      <span className="break-words text-xs text-slate-600">
                        {componentTypeLabel(marker.type)} ·{" "}
                        {constructionStatusLabel(
                          marker.construction_status,
                        )}{" "}
                        · {originLabel(marker.origin)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-slate-500">
                Chưa gắn cấu kiện trên trang này.
              </p>
            )}
          </section>
        ))}
      </div>
    </details>
  );
}
