import { describe, expect, it } from "vitest";
import {
  buildMapTargets,
  contentAspectRatio,
  errorMessage,
  formatShortMapDate,
  hasActiveFilters,
  isPending,
  markerAriaLabel,
  markerDashArray,
  markerLabel,
  markerStrokeColor,
  nextPlacementPoints,
  placementSaveError,
  recordOriginLabel,
  shortSha,
  statusChipClass,
  verificationLabel,
  type Placement,
} from "./drawingMapPanel";
import { ApiError } from "./api";
import { EMPTY_DRAWING_FILTERS, type DrawingMarker } from "./drawingMap";

function marker(overrides: Partial<DrawingMarker> = {}): DrawingMarker {
  return {
    component_id: "c1",
    code: "F-24-25",
    type: "pile",
    points: [[0.2, 0.4]],
    origin: "DESIGN_SCOPE",
    construction_status: "NOT_STARTED",
    ...overrides,
  };
}

function placement(overrides: Partial<Placement> = {}): Placement {
  return {
    componentId: "c1",
    code: "F-24-25",
    type: "pile",
    sheetId: "sheet-1",
    points: [[0.1, 0.2]],
    override: false,
    ...overrides,
  };
}

describe("drawingMapPanel helpers", () => {
  it("formats ISO dates and passes other values through", () => {
    expect(formatShortMapDate("2025-03-09T10:00:00")).toBe("09/03/2025");
    expect(formatShortMapDate("2025-03-09")).toBe("09/03/2025");
    expect(formatShortMapDate("không rõ")).toBe("không rõ");
  });

  it("maps verification and record origin labels", () => {
    expect(verificationLabel("VERIFIED")).toBe("Đã duyệt");
    expect(verificationLabel("NEEDS_REVIEW")).toBe("Chờ duyệt");
    expect(verificationLabel("PENDING")).toBe("PENDING");
    expect(recordOriginLabel("SEED_IMPORT")).toBe("Nhập từ danh mục");
    expect(recordOriginLabel("MANUAL_ENTRY")).toBe("Nhập thủ công");
    expect(recordOriginLabel("OTHER")).toBe("OTHER");
  });

  it("shortens hashes and falls back to a dash", () => {
    expect(shortSha("0123456789abcdef")).toBe("0123456789ab…");
    expect(shortSha(null)).toBe("—");
    expect(shortSha(undefined)).toBe("—");
  });

  it("builds the marker label from code, type, status and origin", () => {
    expect(markerLabel(marker())).toBe(
      "F-24-25 · Cọc · Chưa bắt đầu · Thiết kế",
    );
  });

  it("falls back to the not-started status chip", () => {
    expect(statusChipClass("IN_PROGRESS")).toBe(
      "app-status app-status--in-progress",
    );
    expect(statusChipClass("UNKNOWN")).toBe(
      "app-status app-status--not-started",
    );
  });

  it("detects active filters", () => {
    expect(hasActiveFilters(EMPTY_DRAWING_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...EMPTY_DRAWING_FILTERS, query: "  " })).toBe(
      false,
    );
    expect(hasActiveFilters({ ...EMPTY_DRAWING_FILTERS, type: "pile" })).toBe(
      true,
    );
  });

  it("builds one target per marker using the middle point", () => {
    const targets = buildMapTargets([
      marker({ component_id: "single", points: [[0.1, 0.2]] }),
      marker({
        component_id: "beam",
        type: "beam",
        points: [
          [0.2, 0.2],
          [0.6, 0.6],
        ],
      }),
      marker({ component_id: "invalid", points: [] }),
    ]);
    expect(targets.map((target) => target.marker.component_id)).toEqual([
      "beam",
      "single",
    ]);
    const beam = targets[0];
    // middle index 0, next point 1 -> midpoint of the two end points
    expect([beam.x, beam.y]).toEqual([0.4, 0.4]);
  });

  it("picks compact status colours and full-map design colours", () => {
    expect(markerStrokeColor(marker(), true)).toBe("#64748b");
    expect(markerStrokeColor(marker({ type: "beam" }), false)).toBe("#0f766e");
    expect(markerStrokeColor(marker(), false)).toBe("#0369a1");
    expect(
      markerStrokeColor(marker({ design_group: "Nhóm 2", type: "pile" }), false),
    ).toBe("#b45309");
  });

  it("dashes pending-review and additional-scope markers", () => {
    expect(markerDashArray(marker(), "line")).toBeUndefined();
    expect(markerDashArray(marker({ location_review: true }), "line")).toBe(
      "2 3",
    );
    expect(
      markerDashArray(marker({ position_status: "DRAFT" }), "point"),
    ).toBe("1.5 2");
    expect(
      markerDashArray(marker({ origin: "ADDITIONAL_SCOPE" }), "line"),
    ).toBe("5 3");
    expect(
      markerDashArray(marker({ origin: "ADDITIONAL_SCOPE" }), "point"),
    ).toBe("2 2");
  });

  it("builds aria labels for selection and detail modes", () => {
    expect(
      markerAriaLabel(marker(), { selecting: false }),
    ).toBe("Mở chi tiết F-24-25 · Cọc · Chưa bắt đầu · Thiết kế");
    expect(
      markerAriaLabel(marker({ current_work: "ép cọc" }), {
        selecting: false,
      }),
    ).toContain(", đang làm ép cọc");
    expect(
      markerAriaLabel(marker(), {
        selecting: true,
        selected: true,
        selectable: true,
      }),
    ).toContain("Bỏ chọn");
    expect(
      markerAriaLabel(marker(), {
        selecting: true,
        selected: false,
        selectable: false,
      }),
    ).toContain(", không phù hợp công việc");
  });

  it("distinguishes ApiError and plain errors", () => {
    expect(errorMessage(new ApiError("hỏng", 500))).toBe("hỏng");
    expect(errorMessage(new Error("hỏng"))).toBe("hỏng");
    expect(errorMessage("hỏng")).toBe("Không xác định được lỗi.");
    expect(isPending(new ApiError("x", 404))).toBe(true);
    expect(isPending(new ApiError("x", 405))).toBe(true);
    expect(isPending(new ApiError("x", 501))).toBe(true);
    expect(isPending(new ApiError("x", 500))).toBe(false);
  });

  it("validates placement points per component type", () => {
    expect(placementSaveError(placement())).toBeNull();
    expect(
      placementSaveError(placement({ points: [] })),
    ).toBe("Cọc cần đúng một điểm trên bản vẽ.");
    expect(
      placementSaveError(placement({ type: "beam", points: [[0, 0]] })),
    ).toBe("Dầm cần ít nhất hai điểm để vẽ đường tim.");
    expect(
      placementSaveError(
        placement({
          type: "beam",
          points: [
            [0, 0],
            [0.1, 0.1],
          ],
        }),
      ),
    ).toBeNull();
  });

  it("replaces the pile point, appends beam points and caps at 30", () => {
    expect(
      nextPlacementPoints(placement(), [0.5, 0.5]),
    ).toEqual([[0.5, 0.5]]);
    const beam = placement({
      type: "beam",
      points: [
        [0, 0],
        [0.1, 0.1],
      ],
    });
    expect(nextPlacementPoints(beam, [0.2, 0.2])).toHaveLength(3);
    const full = placement({
      type: "beam",
      points: Array.from({ length: 30 }, () => [0, 0] as [number, number]),
    });
    expect(nextPlacementPoints(full, [1, 1])).toHaveLength(30);
  });

  it("derives the compact viewport aspect from the fitted marker box", () => {
    expect(
      contentAspectRatio(
        { minX: 0.2, minY: 0.2, maxX: 0.8, maxY: 0.6 },
        1.5,
      ),
    ).toBeCloseTo(2.25);
    // Empty or degenerate boxes fall back to the sheet aspect.
    expect(contentAspectRatio(null, 1.25)).toBe(1.25);
    expect(
      contentAspectRatio(
        { minX: 0.5, minY: 0.5, maxX: 0.5, maxY: 0.5 },
        1.25,
      ),
    ).toBe(1.25);
    expect(contentAspectRatio(null, null)).toBe(1.4);
    // A collinear beam is clamped so the card keeps a usable height.
    expect(
      contentAspectRatio(
        { minX: 0, minY: 0.5, maxX: 1, maxY: 0.5 },
        1.5,
      ),
    ).toBe(3);
  });
});
