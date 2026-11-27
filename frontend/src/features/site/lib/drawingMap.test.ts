import { describe, expect, it } from "vitest";
import {
  EMPTY_DRAWING_FILTERS,
  apiRelativePath,
  clampPan,
  clampZoom,
  clientToSheetPoint,
  constructionStatusColor,
  containBox,
  countMarkers,
  filterDrawingSheets,
  pickPrimarySheet,
  pinchView,
  pinchZoom,
  sanitizePoints,
  sheetToClient,
  zoomAroundPoint,
  fitViewToBounds,
  markerBounds,
  viewportFitStep,
  type DrawingSheet,
  type ImageBox,
} from "./drawingMap";

function sheet(overrides: Partial<DrawingSheet> = {}): DrawingSheet {
  return {
    id: "sheet-1",
    title: "Mặt bằng cầu chính",
    drawing: "TK-32",
    page: 38,
    image_url: "/projects/p1/drawing-map/sheet-1/image",
    markers: [
      {
        component_id: "c1",
        code: "F-24-25",
        type: "pile",
        points: [[0.2, 0.3]],
        origin: "DESIGN_SCOPE",
        construction_status: "NOT_STARTED",
      },
      {
        component_id: "c2",
        code: "D-01",
        type: "beam",
        points: [[0.1, 0.1], [0.4, 0.4]],
        origin: "ADDITIONAL_SCOPE",
        construction_status: "COMPLETED",
      },
    ],
    ...overrides,
  };
}

function filters(patch: Partial<typeof EMPTY_DRAWING_FILTERS> = {}) {
  return { ...EMPTY_DRAWING_FILTERS, ...patch };
}

describe("drawing map filters", () => {
  const second = sheet({
    id: "sheet-2",
    title: "Mặt bằng nhịp dẫn",
    drawing: "TK-33",
    page: 39,
    markers: [
      {
        component_id: "c3",
        code: "D-02",
        type: "beam",
        points: [[0.5, 0.5], [0.6, 0.6]],
        origin: "DESIGN_SCOPE",
        construction_status: "IN_PROGRESS",
      },
    ],
  });

  it("keeps every sheet when no filter is active", () => {
    const result = filterDrawingSheets([sheet(), second], filters());
    expect(result.map((item) => item.markers.length)).toEqual([2, 1]);
    expect(countMarkers(result)).toBe(3);
  });

  it("filters markers by type, construction status and repair scope", () => {
    expect(filterDrawingSheets([sheet(), second], filters({ type: "pile" }))).toEqual([
      expect.objectContaining({ id: "sheet-1", markers: [expect.objectContaining({ code: "F-24-25" })] }),
    ]);
    expect(
      filterDrawingSheets([sheet(), second], filters({ status: "COMPLETED" })).flatMap(
        (item) => item.markers.map((marker) => marker.code),
      ),
    ).toEqual(["D-01"]);
    expect(
      filterDrawingSheets([sheet(), second], filters({ origin: "ADDITIONAL_SCOPE" })).flatMap(
        (item) => item.markers.map((marker) => marker.code),
      ),
    ).toEqual(["D-01"]);
  });

  it("matches a drawing/title and keeps its markers, or narrows by component code", () => {
    expect(
      filterDrawingSheets([sheet(), second], filters({ query: "tk-32" }))[0].markers,
    ).toHaveLength(2);
    expect(
      filterDrawingSheets([sheet(), second], filters({ query: "f-24" })).flatMap(
        (item) => item.markers.map((marker) => marker.code),
      ),
    ).toEqual(["F-24-25"]);
    expect(filterDrawingSheets([sheet(), second], filters({ query: "không có" }))).toEqual(
      [],
    );
  });

  it("combines search with marker filters and drops empty sheets", () => {
    expect(
      filterDrawingSheets([sheet(), second], filters({ query: "tk-32", type: "beam" })),
    ).toEqual([
      expect.objectContaining({
        markers: [expect.objectContaining({ code: "D-01" })],
      }),
    ]);
  });
});

describe("normalised overlay geometry", () => {
  it("letterboxes an object-contain image inside its element", () => {
    expect(containBox(1000, 500, 400, 400)).toEqual({
      left: 0,
      top: 100,
      width: 400,
      height: 200,
    });
    expect(containBox(500, 1000, 300, 600)).toEqual({
      left: 0,
      top: 0,
      width: 300,
      height: 600,
    });
    expect(containBox(0, 100, 300, 600)).toBeNull();
  });

  it("clamps points into the image and drops malformed points", () => {
    expect(
      sanitizePoints([
        [-0.5, 1.5],
        [0.25, 0.75],
        [Number.NaN, 0],
        [2, 0, 3] as unknown as [number, number],
      ]),
    ).toEqual([
      [0, 1],
      [0.25, 0.75],
    ]);
    expect(sanitizePoints(undefined)).toEqual([]);
  });
});

describe("zoom and pan limits", () => {
  it("keeps zoom between one and four", () => {
    expect(clampZoom(0.2)).toBe(1);
    expect(clampZoom(2.5)).toBe(2.5);
    expect(clampZoom(9)).toBe(4);
    expect(clampZoom(Number.NaN)).toBe(1);
  });

  it("cannot pan the image away from the viewport", () => {
    expect(clampPan({ x: 90, y: -90 }, 1, 400, 300)).toEqual({ x: 0, y: 0 });
    expect(clampPan({ x: 90, y: -90 }, 2, 400, 300)).toEqual({ x: 90, y: -90 });
    expect(clampPan({ x: 900, y: -900 }, 2, 400, 300)).toEqual({ x: 200, y: -150 });
  });

  it("derives pinch zoom from the distance ratio", () => {
    expect(pinchZoom(1, 100, 200)).toBe(2);
    expect(pinchZoom(3, 100, 200)).toBe(4);
    expect(pinchZoom(2, 0, 200)).toBe(2);
  });
});

it("accepts image paths with or without the API prefix", () => {
  expect(apiRelativePath("/api/v1/projects/p/drawing-map/s/image")).toBe(
    "/projects/p/drawing-map/s/image",
  );
  expect(apiRelativePath("/projects/p/drawing-map/s/image")).toBe(
    "/projects/p/drawing-map/s/image",
  );
});

describe("fit the view to the batch marker bounding box", () => {
  const imageBox: ImageBox = { left: 0, top: 50, width: 400, height: 200 };

  it("fits a centred marker box with 10% padding", () => {
    const view = fitViewToBounds(
      { minX: 0.25, minY: 0.25, maxX: 0.75, maxY: 0.75 },
      imageBox,
      400,
      300,
      0.1,
    );
    expect(view?.zoom).toBeCloseTo(1.6);
    expect(view?.pan.x).toBeCloseTo(0);
    expect(view?.pan.y).toBeCloseTo(0);
  });

  it("centres an off-centre box and clamps pan to the zoom limit", () => {
    const view = fitViewToBounds(
      { minX: 0.01, minY: 0.4, maxX: 0.05, maxY: 0.5 },
      imageBox,
      400,
      300,
      0.1,
    );
    expect(view?.zoom).toBe(4);
    expect(view?.pan).toEqual({ x: 600, y: 40 });
  });

  it("bounds markers defensively and reports an empty sheet", () => {
    expect(markerBounds([])).toBeNull();
    expect(
      markerBounds([
        {
          component_id: "c1", code: "F1", type: "pile", points: [[0.2, 0.3]],
          origin: "DESIGN_SCOPE", construction_status: "COMPLETED",
        },
        {
          component_id: "c2", code: "F2", type: "pile",
          points: [[0.6, 0.7], [0.8, 0.9]],
          origin: "DESIGN_SCOPE", construction_status: "COMPLETED",
        },
      ]),
    ).toEqual({ minX: 0.2, minY: 0.3, maxX: 0.8, maxY: 0.9 });
    expect(fitViewToBounds(null, imageBox, 400, 300, 0.08)).toBeNull();
  });

  it("uses a minimum span for one point and caps zoom at four", () => {
    const view = fitViewToBounds(
      { minX: 0.5, minY: 0.5, maxX: 0.5, maxY: 0.5 },
      imageBox,
      400,
      300,
      0.08,
    );
    expect(view?.zoom).toBe(4);
    expect(view?.pan).toEqual({ x: 0, y: 0 });
  });
});

describe("viewport fit happens once per sheet", () => {
  it("fits on open, then ignores metrics, data and selection noise", () => {
    const opened = viewportFitStep(
      { activeSheetKey: "", fittedSheetKey: null },
      { type: "open", sheetKey: "sheet-1", imageReady: true },
    );
    expect(opened.fit).toBe(true);
    expect(opened.state.fittedSheetKey).toBe("sheet-1");

    for (const event of [
      { type: "metrics" },
      { type: "data" },
      { type: "selection" },
    ] as const) {
      const step = viewportFitStep(opened.state, event);
      expect(step.fit).toBe(false);
      expect(step.state).toEqual(opened.state);
    }
  });

  it("never refits after the user moves the view", () => {
    const opened = viewportFitStep(
      { activeSheetKey: "", fittedSheetKey: null },
      { type: "open", sheetKey: "sheet-1", imageReady: true },
    );
    const moved = viewportFitStep(opened.state, { type: "gesture" });
    expect(moved.fit).toBe(false);
    expect(moved.state.fittedSheetKey).toBe("sheet-1");
    expect(
      viewportFitStep(moved.state, {
        type: "open",
        sheetKey: "sheet-1",
        imageReady: true,
      }).fit,
    ).toBe(false);
  });

  it("waits for the image and fits a newly opened sheet", () => {
    const notReady = viewportFitStep(
      { activeSheetKey: "sheet-1", fittedSheetKey: "sheet-1" },
      { type: "open", sheetKey: "sheet-2", imageReady: false },
    );
    expect(notReady.fit).toBe(false);
    expect(notReady.state.activeSheetKey).toBe("sheet-2");
    const ready = viewportFitStep(notReady.state, {
      type: "open",
      sheetKey: "sheet-2",
      imageReady: true,
    });
    expect(ready.fit).toBe(true);
  });

  it("fits again only on an explicit reset request", () => {
    const state = { activeSheetKey: "sheet-1", fittedSheetKey: "sheet-1" };
    expect(viewportFitStep(state, { type: "reset", imageReady: true }).fit).toBe(
      true,
    );
    expect(
      viewportFitStep(state, { type: "reset", imageReady: false }).fit,
    ).toBe(false);
  });
});

describe("compact overview map helpers", () => {
  it("maps construction status to the existing colour tokens", () => {
    expect(constructionStatusColor("NOT_STARTED")).toBe("#64748b");
    expect(constructionStatusColor("IN_PROGRESS")).toBe("#b45309");
    expect(constructionStatusColor("COMPLETED")).toBe("#15803d");
    expect(constructionStatusColor("BLOCKED")).toBe("#b91c1c");
    expect(constructionStatusColor("UNKNOWN")).toBe("#64748b");
  });

  it("picks the main-zone sheet and leaves Bunke for the switcher", () => {
    const main = sheet({
      id: "main",
      markers: [{
        component_id: "c1", code: "F1", type: "pile", zone: "Cầu chính",
        points: [[0.1, 0.1]], origin: "DESIGN_SCOPE", construction_status: "COMPLETED",
      }],
    });
    const bunke = sheet({
      id: "bunke",
      markers: [{
        component_id: "c2", code: "B1", type: "pile", zone: "Bunke",
        points: [[0.2, 0.2]], origin: "DESIGN_SCOPE", construction_status: "IN_PROGRESS",
      }],
    });
    expect(pickPrimarySheet([bunke, main], "Cầu chính")?.id).toBe("main");
    expect(pickPrimarySheet([bunke, main], "Bunke")?.id).toBe("bunke");
    expect(pickPrimarySheet([bunke, main], null)?.id).toBe("bunke");
    expect(pickPrimarySheet([], "Cầu chính")).toBeNull();
  });
});

describe("placement point mapping", () => {
  const imageBox = { left: 10, top: 20, width: 400, height: 200 };
  const rect = { left: 0, top: 0, width: 500, height: 300 };

  it("round-trips a normalised point through zoom and pan", () => {
    const view = { zoom: 2, pan: { x: 30, y: -20 } };
    const [u, v] = [0.25, 0.75];
    const screenX =
      (imageBox.left + u * imageBox.width - rect.width / 2) * view.zoom +
      rect.width / 2 +
      view.pan.x;
    const screenY =
      (imageBox.top + v * imageBox.height - rect.height / 2) * view.zoom +
      rect.height / 2 +
      view.pan.y;
    const point = clientToSheetPoint(
      { x: screenX, y: screenY },
      rect,
      imageBox,
      view,
    );
    expect(point?.[0]).toBeCloseTo(u);
    expect(point?.[1]).toBeCloseTo(v);
  });

  it("rejects taps outside the drawn image and unusable geometry", () => {
    const view = { zoom: 1, pan: { x: 0, y: 0 } };
    expect(clientToSheetPoint({ x: 2, y: 2 }, rect, imageBox, view)).toBeNull();
    expect(
      clientToSheetPoint({ x: 250, y: 150 }, rect, imageBox, {
        zoom: 0,
        pan: { x: 0, y: 0 },
      }),
    ).toEqual([0.6, 0.65]);
    expect(
      clientToSheetPoint(
        { x: 0, y: 0 },
        { ...rect, width: 0 },
        imageBox,
        view,
      ),
    ).toBeNull();
  });
});

describe("gesture view helpers", () => {
  const rect = { left: 0, top: 0, width: 400, height: 300 };
  const imageBox = { left: 0, top: 0, width: 400, height: 300 };

  it("round-trips normalized points through the forward transform", () => {
    const view = { zoom: 2, pan: { x: 31, y: -18 } };
    const client = sheetToClient([0.25, 0.75], rect, imageBox, view);
    const point = clientToSheetPoint(
      { x: client[0], y: client[1] },
      rect,
      imageBox,
      view,
    );
    expect(point?.[0]).toBeCloseTo(0.25);
    expect(point?.[1]).toBeCloseTo(0.75);
  });

  it("zooms around the tapped point without moving it", () => {
    const start = { zoom: 1, pan: { x: 0, y: 0 } };
    const tap = { x: 280, y: 90 };
    const before = clientToSheetPoint(tap, rect, imageBox, start);
    const next = zoomAroundPoint(start, tap, 2, rect);
    const after = clientToSheetPoint(tap, rect, imageBox, next);
    expect(after?.[0]).toBeCloseTo(before?.[0] ?? 0);
    expect(after?.[1]).toBeCloseTo(before?.[1] ?? 0);
    expect(next.zoom).toBe(2);
  });

  it("keeps the sheet point under the pinch midpoint", () => {
    const start = { zoom: 1, pan: { x: 0, y: 0 } };
    const startMid = { x: 200, y: 150 };
    const currentMid = { x: 230, y: 165 };
    const before = clientToSheetPoint(startMid, rect, imageBox, start);
    const next = pinchView(start, startMid, currentMid, 2, rect);
    const after = sheetToClient(before!, rect, imageBox, next);
    expect(after[0]).toBeCloseTo(currentMid.x);
    expect(after[1]).toBeCloseTo(currentMid.y);
    expect(next.zoom).toBe(2);
  });
});
