import { describe, expect, it } from "vitest";
import {
  abbreviateWorkName,
  buildMapTargets,
  contentAspectRatio,
  errorMessage,
  formatShortMapDate,
  hasActiveFilters,
  hitTestMarkers,
  isPending,
  labelModeForZoom,
  layoutMarkerLabels,
  markerAriaLabel,
  markerDashArray,
  markerLabel,
  markerStrokeColor,
  nextPlacementPoints,
  placementSaveError,
  pointToSegmentDistance,
  recordOriginLabel,
  shortSha,
  statusChipClass,
  verificationLabel,
  type MapTarget,
  type Placement,
  type ScreenTarget,
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

describe("work labels and hit testing", () => {
  function mapTarget(
    overrides: Partial<DrawingMarker> = {},
    points: Array<[number, number]> = [[0.5, 0.5]],
    x = points[0][0],
    y = points[0][1],
  ): MapTarget {
    return { marker: marker(overrides), points, x, y };
  }

  it("abbreviates common work names and falls back to three words", () => {
    expect(
      abbreviateWorkName("Đục bê tông om vỡ dày trung bình t = 3 cm"),
    ).toBe("Đục BT");
    expect(abbreviateWorkName("Tẩy gỉ")).toBe("Tẩy gỉ");
    expect(abbreviateWorkName("Vệ sinh")).toBe("Vệ sinh");
    expect(abbreviateWorkName("Epoxy")).toBe("Epoxy");
    expect(abbreviateWorkName("Cát nhám")).toBe("Cát nhám");
    expect(abbreviateWorkName("Ván khuôn")).toBe("Ván khuôn");
    expect(abbreviateWorkName("Vữa KCN")).toBe("Vữa KCN");
    expect(abbreviateWorkName("Sợi TT L1")).toBe("Sợi TT L1");
    expect(abbreviateWorkName("Sơn UV")).toBe("Sơn UV");
    expect(abbreviateWorkName("Đổ thải")).toBe("Đổ thải");
    expect(abbreviateWorkName("Gia công cốt thép chờ")).toBe(
      "Gia công cốt",
    );
    expect(abbreviateWorkName("")).toBeNull();
  });

  it("switches label density by zoom", () => {
    expect(labelModeForZoom(1)).toBe("none");
    expect(labelModeForZoom(1.04)).toBe("none");
    expect(labelModeForZoom(1.05)).toBe("code");
    expect(labelModeForZoom(1.29)).toBe("code");
    expect(labelModeForZoom(1.3)).toBe("full");
  });

  it("shows short work under the code and skips colliding labels", () => {
    const first = mapTarget(
      {
        code: "A1",
        current_work_name: "Đục BT om vỡ t=3cm",
        current_work_status: "IN_PROGRESS",
      },
      [[0.5, 0.5]],
    );
    const second = mapTarget(
      { code: "A2", current_work_name: "Vệ sinh" },
      [[0.5, 0.5]],
    );
    const labels = layoutMarkerLabels(
      [first, second],
      "full",
      1.3,
      { width: 1000, height: 1000 },
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].text).toBe("A1 · Đục BT");
    expect(labels[0].status).toBe("IN_PROGRESS");
    const codeLabels = layoutMarkerLabels(
      [second],
      "code",
      1.1,
      { width: 1000, height: 1000 },
    );
    expect(codeLabels[0].text).toBe("A2");
  });

  it("measures point-to-segment distance", () => {
    expect(
      pointToSegmentDistance([5, 5], [0, 0], [10, 0]),
    ).toBeCloseTo(5);
    expect(
      pointToSegmentDistance([-2, 0], [0, 0], [10, 0]),
    ).toBeCloseTo(2);
    expect(
      pointToSegmentDistance([1, 1], [2, 2], [2, 2]),
    ).toBeCloseTo(Math.SQRT2);
  });

  it("prefers a beam when the tap is closer to its line than a pile center", () => {
    const pile: ScreenTarget = {
      marker: marker({ code: "P1", type: "pile" }),
      points: [[100, 100]],
    };
    const beam: ScreenTarget = {
      marker: marker({ code: "D1", type: "beam" }),
      points: [
        [0, 120],
        [200, 120],
      ],
    };
    const hits = hitTestMarkers([pile, beam], [100, 118]);
    expect(hits.map((hit) => hit.marker.code)).toEqual(["D1"]);
    expect(hitTestMarkers([pile, beam], [103, 101])[0].marker.code).toBe("P1");
  });

  it("returns both candidates when their distances are nearly equal", () => {
    const left: ScreenTarget = {
      marker: marker({ code: "P1", type: "pile" }),
      points: [[100, 100]],
    };
    const right: ScreenTarget = {
      marker: marker({ code: "P2", type: "pile" }),
      points: [[102, 100]],
    };
    expect(
      hitTestMarkers([left, right], [101, 100]).map((hit) => hit.marker.code),
    ).toEqual(["P1", "P2"]);
    expect(hitTestMarkers([left, right], [300, 300])).toEqual([]);
  });
});
