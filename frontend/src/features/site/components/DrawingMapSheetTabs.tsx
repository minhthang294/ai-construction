/** Sheet tabs for the drawing map panel. */

import { FOCUS_RING, type Placement } from "../lib/drawingMapPanel";
import type { DrawingSheet } from "../lib/drawingMap";

type Props = {
  filteredSheets: ReadonlyArray<DrawingSheet>;
  activeSheet: DrawingSheet | null;
  placement: Placement | null;
  setActiveSheetId: (sheetId: string) => void;
};

export default function DrawingMapSheetTabs({
  filteredSheets,
  activeSheet,
  placement,
  setActiveSheetId,
}: Props) {
  return (
    <div
      role="group"
      aria-label="Chọn trang bản vẽ"
      className="flex gap-2 overflow-x-auto pb-1"
    >
      {filteredSheets.map((sheet) => {
        const selected = sheet.id === activeSheet?.id;
        return (
          <button
            key={sheet.id}
            type="button"
            aria-pressed={selected}
            disabled={Boolean(placement)}
            className={`min-h-11 min-w-0 shrink-0 rounded-lg border px-3 text-left text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
              selected
                ? "border-slate-700 bg-slate-800 text-white"
                : "border-slate-300 bg-white text-slate-800"
            } ${FOCUS_RING}`}
            onClick={() => setActiveSheetId(sheet.id)}
          >
            <span className="block max-w-56 truncate font-semibold">
              {sheet.title}
            </span>
            <span
              className={`block text-xs ${
                selected ? "text-slate-200" : "text-slate-500"
              }`}
            >
              {sheet.drawing} · trang {sheet.page}
            </span>
          </button>
        );
      })}
    </div>
  );
}
