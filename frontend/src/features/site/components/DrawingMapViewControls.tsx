/** Zoom controls and legend for the drawing map canvas. */

import {
  ACCEPTANCE_OUTLINE_COLOR,
  MAX_ZOOM,
  MIN_ZOOM,
  constructionStatusColor,
  type View,
} from "../lib/drawingMap";
import { BUTTON, FOCUS_RING } from "../lib/drawingMapPanel";

type Props = {
  compact: boolean;
  view: View;
  zoomBy: (delta: number) => void;
  resetView: () => void;
  showWholeSheet: () => void;
};

export default function DrawingMapViewControls({
  compact,
  view,
  zoomBy,
  resetView,
  showWholeSheet,
}: Props) {
  return (
    <>
      <div
        role="group"
        aria-label="Thu phóng bản vẽ"
        className="flex flex-nowrap items-center gap-1 border-t border-slate-200 bg-white px-2 py-1.5"
      >
        <button
          type="button"
          aria-label="Thu nhỏ bản vẽ"
          title="Thu nhỏ"
          className={`${BUTTON} min-w-11 shrink-0 px-0 ${FOCUS_RING}`}
          disabled={view.zoom <= MIN_ZOOM}
          onClick={() => zoomBy(-0.5)}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 20 20"
            className="mx-auto h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M5 10h10" />
          </svg>
        </button>
        <span className="min-w-8 shrink-0 text-center text-[11px] font-semibold tabular-nums text-slate-600">
          {Math.round(view.zoom * 100)}%
        </span>
        <button
          type="button"
          aria-label="Phóng to bản vẽ"
          title="Phóng to"
          className={`${BUTTON} min-w-11 shrink-0 px-0 ${FOCUS_RING}`}
          disabled={view.zoom >= MAX_ZOOM}
          onClick={() => zoomBy(0.5)}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 20 20"
            className="mx-auto h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M10 5v10M5 10h10" />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Vừa khung theo phạm vi cấu kiện"
          title="Vừa khung theo phạm vi cấu kiện"
          className={`${BUTTON} min-w-11 shrink-0 px-0 ${FOCUS_RING}`}
          onClick={resetView}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 20 20"
            className="mx-auto h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M8 4H4v4M12 4h4v4M8 16H4v-4M12 16h4v-4" />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Xem toàn tờ bản vẽ"
          title="Xem toàn tờ bản vẽ"
          className={`${BUTTON} min-w-11 shrink-0 px-0 ${FOCUS_RING}`}
          onClick={showWholeSheet}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 20 20"
            className="mx-auto h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M6 3h5l4 4v10H6z" />
            <path d="M11 3v4h4" />
          </svg>
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-200 p-3 text-xs text-slate-600">
        {compact ? (
          <>
            <span>Kéo để di chuyển, chụm hai ngón hoặc dùng +/−.</span>
            {[
              ["NOT_STARTED", "Chưa bắt đầu"],
              ["IN_PROGRESS", "Đang thi công"],
              ["COMPLETED", "Hoàn thành"],
              ["BLOCKED", "Tạm dừng"],
            ].map(([status, label]) => (
              <span key={status} className="inline-flex items-center gap-1">
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: constructionStatusColor(status) }}
                />
                {label}
              </span>
            ))}
            <span className="inline-flex items-center gap-1">
              <span
                aria-hidden="true"
                className="h-3 w-3 rounded-full border-2"
                style={{ borderColor: ACCEPTANCE_OUTLINE_COLOR }}
              />
              Đã nghiệm thu
            </span>
          </>
        ) : (
          <>
            <span>Kéo để di chuyển.</span>
            <span>Chụm hai ngón hoặc dùng nút +/− để thu phóng.</span>
            <span className="inline-flex items-center gap-1"><span className="h-0.5 w-3 bg-teal-700" /> Dầm · nét mảnh</span>
            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-teal-700" /> Nhóm 1</span>
            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-amber-700" /> Nhóm 2</span>
            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-purple-700" /> Nhóm 3</span>
            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-dashed border-slate-600" /> Vị trí chờ rà soát</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full border border-dashed border-sky-600" />
              Nét đứt: phạm vi phát sinh.
            </span>
          </>
        )}
      </div>
    </>
  );
}
