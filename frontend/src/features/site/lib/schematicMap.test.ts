import { describe, expect, it } from "vitest";
import {
  buildSchematicPlans,
  parseSchematicCode,
  type SchematicInput,
} from "./schematicMap";

function item(overrides: Partial<SchematicInput> = {}): SchematicInput {
  return {
    id: overrides.id ?? "c1",
    code: overrides.code ?? "I49",
    type: overrides.type ?? "pile",
    zone: overrides.zone ?? "Cầu chính",
    segment: overrides.segment ?? 2,
    status: overrides.status ?? "NOT_STARTED",
    accepted: overrides.accepted ?? false,
    ...overrides,
  };
}

describe("schematic code parsing", () => {
  it("parses pile, horizontal and vertical beams", () => {
    expect(parseSchematicCode("I49")).toEqual({
      kind: "pile",
      row: "I",
      axis: 49,
    });
    expect(parseSchematicCode("F-66-67")).toEqual({
      kind: "beam",
      row: "F",
      axis: 66,
      axisEnd: 67,
    });
    expect(parseSchematicCode("A-B-153")).toEqual({
      kind: "vertical",
      row: "A",
      rowEnd: "B",
      axis: 153,
    });
    expect(parseSchematicCode("I-96")).toEqual({
      kind: "beam",
      row: "I",
      axis: 96,
      axisEnd: 96,
    });
  });

  it("keeps corners, fenders and unknown codes distinct", () => {
    expect(parseSchematicCode("Q-270")).toEqual({
      kind: "corner",
      row: "Q",
      axis: 270,
    });
    expect(parseSchematicCode("K-111-112")).toEqual({
      kind: "fender",
      row: "K",
      axis: 111,
      axisEnd: 112,
    });
    expect(parseSchematicCode("K-1")).toEqual({
      kind: "fender",
      row: "K",
      axis: 1,
      axisEnd: 1,
    });
    expect(parseSchematicCode("???", "beam")).toEqual({
      kind: "unknown",
      code: "???",
    });
  });
});

describe("schematic plan layout", () => {
  it("compresses unused axis gaps into even columns", () => {
    const [plan] = buildSchematicPlans([
      item({ id: "a", code: "I5" }),
      item({ id: "b", code: "I20" }),
      item({ id: "c", code: "I100" }),
    ]);
    expect(plan.axes.map((axis) => axis.value)).toEqual([5, 20, 100]);
    const gapOne = plan.axes[1].x - plan.axes[0].x;
    const gapTwo = plan.axes[2].x - plan.axes[1].x;
    expect(gapOne).toBe(gapTwo);
  });

  it("draws a horizontal beam between its two axes", () => {
    const [plan] = buildSchematicPlans([
      item({ id: "p1", code: "F66" }),
      item({ id: "p2", code: "F67" }),
      item({ id: "b1", code: "F-66-67", type: "beam" }),
    ]);
    const beam = plan.markers.find((marker) => marker.componentId === "b1");
    expect(beam?.kind).toBe("beam");
    expect(beam?.points).toHaveLength(2);
    expect(beam?.points[0][1]).toBeCloseTo(beam?.points[1][1] ?? 0);
    expect(beam?.points[0][0]).toBeLessThan(beam?.points[1][0] ?? 1);
  });

  it("orders main deck rows top-to-bottom and places Bunke below", () => {
    const [plan] = buildSchematicPlans([
      item({ id: "i", code: "I10" }),
      item({ id: "h", code: "H10" }),
      item({ id: "g", code: "G10" }),
      item({ id: "f", code: "F10" }),
      item({ id: "e", code: "E10", zone: "Bunke" }),
      item({ id: "d", code: "D10", zone: "Bunke" }),
    ]);
    expect(plan.rows.filter((row) => row.main).map((row) => row.key)).toEqual([
      "I",
      "H",
      "G",
      "F",
    ]);
    const bunkeRows = plan.rows.filter((row) => !row.main);
    expect(bunkeRows.map((row) => row.key)).toEqual(["E", "D"]);
    expect(bunkeRows[0].y).toBeGreaterThan(
      plan.rows.filter((row) => row.main).at(-1)?.y ?? 0,
    );
    expect(plan.title).toContain("Bunke");
    expect(plan.bunke).not.toBeNull();
  });

  it("aligns a Bunke block with shared axes and separates disjoint axes", () => {
    const shared = buildSchematicPlans([
      item({ id: "f", code: "F10" }),
      item({ id: "e", code: "E10", zone: "Bunke" }),
    ])[0];
    const mainAxis = shared.axes.find((axis) => axis.value === 10);
    const bunkeRow = shared.rows.find((row) => row.key === "E");
    const bunkeMarker = shared.markers.find(
      (marker) => marker.componentId === "e",
    );
    expect(bunkeMarker?.points[0][0]).toBeCloseTo(
      mainAxis?.x ? mainAxis.x / shared.width : 0,
    );
    expect(bunkeRow?.y).toBeGreaterThan(0);

    const disjoint = buildSchematicPlans([
      item({ id: "f", code: "F10" }),
      item({ id: "e", code: "E500", zone: "Bunke" }),
    ])[0];
    const mainX = disjoint.axes.find((axis) => axis.value === 10)?.x ?? 0;
    const bunkeX = disjoint.axes.find((axis) => axis.value === 500)?.x ?? 0;
    expect(disjoint.bunkeGap).toBe(true);
    expect(bunkeX).toBeGreaterThan(mainX);
  });

  it("normalises every point inside the plan bounds", () => {
    const [plan] = buildSchematicPlans([
      item({ id: "p", code: "I49" }),
      item({ id: "b", code: "F-48-50", type: "beam" }),
      item({ id: "v", code: "I-H-49", type: "beam" }),
      item({ id: "q", code: "Q-270", type: "beam", zone: "Cầu dẫn" }),
      item({ id: "k", code: "K-111-112", type: "beam" }),
    ]);
    for (const marker of plan.markers) {
      for (const [x, y] of marker.points) {
        expect(x).toBeGreaterThanOrEqual(0);
        expect(x).toBeLessThanOrEqual(1);
        expect(y).toBeGreaterThanOrEqual(0);
        expect(y).toBeLessThanOrEqual(1);
      }
    }
  });
});
