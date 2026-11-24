import { describe, expect, it } from "vitest";
import {
  EMPTY_DRAWING_FILTERS,
  apiRelativePath,
  clampPan,
  clampZoom,
  constructionStatusColor,
  containBox,
  countMarkers,
  filterDrawingSheets,
  pickPrimarySheet,
  pinchZoom,
  sanitizePoints,
  type DrawingSheet,
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
