/** Draft placement controls shown while placing a component on the map. */

import type { DrawingSheet } from "../lib/drawingMap";
import {
  BUTTON,
  FOCUS_RING,
  PRIMARY_BUTTON,
  type Placement,
} from "../lib/drawingMapPanel";

type Props = {
  placement: Placement;
  activeSheet: DrawingSheet | null;
  placementBusy: boolean;
  placementError: string | null;
  savePlacement: () => void;
  cancelPlacement: () => void;
  removeLastPlacementPoint: () => void;
};

export default function DrawingMapPlacementPanel({
  placement,
  activeSheet,
  placementBusy,
  placementError,
  savePlacement,
  cancelPlacement,
  removeLastPlacementPoint,
}: Props) {
  return (
    <section className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p className="font-semibold">
        {placement.override ? "Ghi đè vị trí" : "Đặt vị trí"} ·{" "}
        <span className="font-mono">{placement.code}</span>
      </p>
      <p className="mt-1 text-xs leading-5">
        {placement.sheetId
          ? `Trang đang đặt: ${activeSheet?.title ?? placement.sheetId}. `
          : "Hãy mở một trang bản vẽ còn hiển thị. "}
        {placement.type === "pile"
          ? "Chạm một điểm lên cọc, kéo điểm để chỉnh."
          : `Chạm ít nhất hai điểm dọc theo dầm (${placement.points.length} điểm), kéo từng điểm để chỉnh.`}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          className={`${PRIMARY_BUTTON} ${FOCUS_RING}`}
          disabled={
            placementBusy ||
            !placement.sheetId ||
            (placement.type === "pile"
              ? placement.points.length !== 1
              : placement.points.length < 2)
          }
          onClick={() => void savePlacement()}
        >
          {placementBusy ? "Đang lưu…" : "Lưu vị trí nháp"}
        </button>
        {placement.type === "beam" && placement.points.length > 0 ? (
          <button
            type="button"
            className={`${BUTTON} ${FOCUS_RING}`}
            disabled={placementBusy}
            onClick={removeLastPlacementPoint}
          >
            Xóa điểm cuối
          </button>
        ) : null}
        <button
          type="button"
          className={`${BUTTON} ${FOCUS_RING}`}
          disabled={placementBusy}
          onClick={cancelPlacement}
        >
          Hủy đặt vị trí
        </button>
      </div>
      {placementError ? (
        <p role="alert" className="mt-2 text-xs text-red-800">
          {placementError}
        </p>
      ) : null}
    </section>
  );
}
