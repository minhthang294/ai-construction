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
  it("draws every axis between the first and last, evenly spaced", () => {
    const [plan] = buildSchematicPlans([
      item({ id: "a", code: "I5" }),
      item({ id: "b", code: "I8" }),
    ]);
    expect(plan.axes.map((axis) => axis.value)).toEqual([5, 6, 7, 8]);
    const gaps = plan.axes.slice(1).map((axis, i) => axis.x - plan.axes[i].x);
    expect(new Set(gaps).size).toBe(1);
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
    expect(bunkeRows.map((row) => row.key)).toEqual(["E", "D", "C", "B", "A"]);
    expect(bunkeRows[0].y).toBeGreaterThan(
      plan.rows.filter((row) => row.main).at(-1)?.y ?? 0,
    );
    expect(plan.title).toContain("Bunke");
    expect(plan.bunke).not.toBeNull();
  });

  it("uses reviewed anchors for the Bunke sub-grid inside the main width", () => {
    const plan = buildSchematicPlans([
      item({ id: "a49", code: "I49" }),
      item({ id: "a50", code: "I50" }),
      item({ id: "a66", code: "F66" }),
      item({ id: "a67", code: "F67" }),
      item({ id: "a68", code: "F68" }),
      item({ id: "a76", code: "F76" }),
      item({ id: "a81", code: "F81" }),
      item({ id: "b152", code: "A152", zone: "Bunke" }),
      item({ id: "b153", code: "B153", zone: "Bunke" }),
      item({ id: "b154", code: "D154", zone: "Bunke" }),
      item({ id: "b155", code: "E155", zone: "Bunke" }),
      item({ id: "b156", code: "A156", zone: "Bunke" }),
      item({ id: "b157", code: "B157", zone: "Bunke" }),
    ])[0];
    const x = new Map(plan.axes.map((axis) => [axis.value, axis.x]));
    const bx = new Map(plan.bunkeAxes.map((axis) => [axis.value, axis.x]));
    // Fractional anchors from the owner-approved PD2 sketch.
    const gap = (x.get(50) ?? 0) - (x.get(49) ?? 0);
    const at = (axis: number) => (x.get(49) ?? 0) + (axis - 49) * gap;
    expect(bx.get(152)).toBeCloseTo(at(49.75));
    expect(bx.get(153)).toBeCloseTo(at(64.3));
    expect(bx.get(154)).toBeCloseTo(at(66.9));
    expect(bx.get(155)).toBeCloseTo(at(69.6));
    expect(bx.get(156)).toBeCloseTo(at(77.1));
    expect(bx.get(157)).toBeCloseTo(at(79.7));
    expect(plan.bunke?.x0).toBeLessThan(x.get(50) ?? 0);
    expect(plan.bunke?.x1).toBeGreaterThan(at(79.7));
    expect(
      plan.bunkeBlocks.map((block) => block.axes.map((axis) => axis.value)),
    ).toEqual([[152], [153, 154, 155], [156, 157]]);
  });

  it("keeps a Bunke-only plan compact instead of a right-side block", () => {
    const plan = buildSchematicPlans([
      item({ id: "b152", code: "A152", zone: "Bunke" }),
      item({ id: "b153", code: "B153", zone: "Bunke" }),
    ])[0];
    expect(plan.bunke).not.toBeNull();
    const xs = plan.bunkeAxes.map((axis) => axis.x);
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThan(
      (xs.length + 1) * 46,
    );
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
