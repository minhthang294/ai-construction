/** Code-derived schematic layout for one construction segment. */

export type SchematicInput = {
  id: string;
  code: string;
  type: "pile" | "beam";
  zone: string;
  segment: number;
  status: string;
  accepted: boolean;
  workName?: string | null;
  designGroup?: string | null;
};

export type ParsedCode =
  | { kind: "pile"; row: string; axis: number }
  | { kind: "beam"; row: string; axis: number; axisEnd: number }
  | { kind: "vertical"; row: string; rowEnd: string; axis: number }
  | { kind: "corner"; row: string; axis: number }
  | { kind: "fender"; row: string; axis: number; axisEnd: number }
  | { kind: "unknown"; code: string };

export type SchematicMarker = {
  componentId: string;
  code: string;
  type: "pile" | "beam";
  kind: ParsedCode["kind"];
  points: Array<[number, number]>;
  row: string;
};

export type SchematicPlan = {
  key: string;
  title: string;
  zone: string;
  segment: number;
  width: number;
  height: number;
  axes: Array<{ value: number; x: number }>;
  rows: Array<{ key: string; y: number; main: boolean }>;
  bunke: { x0: number; y0: number; x1: number; y1: number } | null;
  markers: SchematicMarker[];
  /** Set when the plan deliberately separates a disjoint Bunke axis block. */
  bunkeGap: boolean;
};

const MAIN_ROWS: Record<string, string[]> = {
  "Cầu chính": ["I", "H", "G", "F"],
  "Cầu dẫn": ["N", "O", "P", "Q", "M"],
};
const BUNKE_ROWS = ["E", "D", "C", "B", "A"];
const BUNKE_ROW_SET = new Set(BUNKE_ROWS);

const LEFT = 66;
const TOP = 56;
const AXIS_GAP = 46;
const ROW_GAP = 64;
const BLOCK_GAP = 42;
const RIGHT = 44;
const BOTTOM = 44;
const AXIS_BUBBLE_Y = 28;
const GAP_SLOTS = 4;

export function parseSchematicCode(
  code: string,
  type: "pile" | "beam" = "beam",
): ParsedCode {
  const value = (code || "").trim().toUpperCase().replace(/\s+/g, "");
  let match = /^([A-Z])(\d+)$/.exec(value);
  if (match) {
    return { kind: "pile", row: match[1], axis: Number(match[2]) };
  }
  match = /^K-(\d+)(?:-(\d+))?$/.exec(value);
  if (match) {
    const axis = Number(match[1]);
    return {
      kind: "fender",
      row: "K",
      axis,
      axisEnd: match[2] ? Number(match[2]) : axis,
    };
  }
  match = /^Q-(\d+)$/.exec(value);
  if (match) {
    return { kind: "corner", row: "Q", axis: Number(match[1]) };
  }
  match = /^([A-Z])-(\d+)-(\d+)$/.exec(value);
  if (match) {
    return {
      kind: "beam",
      row: match[1],
      axis: Number(match[2]),
      axisEnd: Number(match[3]),
    };
  }
  match = /^([A-Z])-([A-Z])-(\d+)$/.exec(value);
  if (match) {
    return {
      kind: "vertical",
      row: match[1],
      rowEnd: match[2],
      axis: Number(match[3]),
    };
  }
  match = /^([A-Z])-(\d+)$/.exec(value);
  if (match) {
    const axis = Number(match[2]);
    return { kind: "beam", row: match[1], axis, axisEnd: axis };
  }
  return { kind: "unknown", code: value };
}

function isBunke(item: SchematicInput, parsed: ParsedCode): boolean {
  if (item.zone === "Bunke") return true;
  const row = "row" in parsed ? parsed.row : "";
  return item.zone === "Cầu chính" && BUNKE_ROW_SET.has(row);
}

function groupComponents(
  components: ReadonlyArray<SchematicInput>,
): Map<string, SchematicInput[]> {
  const groups = new Map<string, SchematicInput[]>();
  for (const item of components) {
    const key = `${item.zone}|${item.segment}`;
    const list = groups.get(key) ?? [];
    list.push(item);
    groups.set(key, list);
  }
  const mainKeys = [...groups.keys()].filter((key) =>
    key.startsWith("Cầu chính|"),
  );
  const bunkeKeys = [...groups.keys()].filter((key) => key.startsWith("Bunke|"));
  if (mainKeys.length === 1 && bunkeKeys.length) {
    const target = groups.get(mainKeys[0]) ?? [];
    for (const key of bunkeKeys) {
      target.push(...(groups.get(key) ?? []));
      groups.delete(key);
    }
    groups.set(mainKeys[0], target);
  }
  return groups;
}

export function buildSchematicPlans(
  components: ReadonlyArray<SchematicInput>,
): SchematicPlan[] {
  return [...groupComponents(components).entries()]
    .map(([key, items]) => buildPlan(key, items))
    .sort((left, right) =>
      left.zone.localeCompare(right.zone, "vi") || left.segment - right.segment,
    );
}

function buildPlan(key: string, items: ReadonlyArray<SchematicInput>): SchematicPlan {
  const zone = key.split("|")[0];
  const segment = Number(key.split("|")[1]) || 0;
  const parsed = items.map((item) => ({
    item,
    code: parseSchematicCode(item.code, item.type),
  }));
  const mainCodes = parsed.filter(({ item, code }) => !isBunke(item, code));
  const bunkeCodes = parsed.filter(({ item, code }) => isBunke(item, code));

  const axisOf = (code: ParsedCode): number[] => {
    if (code.kind === "pile" || code.kind === "corner") return [code.axis];
    if (code.kind === "beam" || code.kind === "fender") {
      return code.axisEnd !== code.axis ? [code.axis, code.axisEnd] : [code.axis];
    }
    if (code.kind === "vertical") return [code.axis];
    return [];
  };
  const mainAxes = [
    ...new Set(mainCodes.flatMap(({ code }) => axisOf(code))),
  ].sort((a, b) => a - b);
  const bunkeAxes = [
    ...new Set(bunkeCodes.flatMap(({ code }) => axisOf(code))),
  ].sort((a, b) => a - b);
  const sharedAxes = bunkeAxes.filter((axis) => mainAxes.includes(axis));

  let axisValues: number[] = [];
  let bunkeOffset = 0;
  let bunkeGap = false;
  if (!bunkeAxes.length || sharedAxes.length) {
    axisValues = [...new Set([...mainAxes, ...bunkeAxes])].sort(
      (a, b) => a - b,
    );
  } else {
    bunkeGap = true;
    bunkeOffset = mainAxes.length + GAP_SLOTS;
    axisValues = [...mainAxes, ...bunkeAxes];
  }
  const axisX = new Map<number, number>();
  axisValues.forEach((axis, index) => {
    const xIndex =
      bunkeGap && !mainAxes.includes(axis)
        ? bunkeOffset + bunkeAxes.indexOf(axis)
        : index;
    axisX.set(axis, LEFT + xIndex * AXIS_GAP);
  });
  const axes = axisValues.map((value) => ({
    value,
    x: axisX.get(value) ?? LEFT,
  }));

  const preferred = MAIN_ROWS[zone] ?? [];
  const presentMainRows = [
    ...new Set(mainCodes.map(({ code }) => ("row" in code ? code.row : ""))),
  ].filter(Boolean);
  const mainRowOrder = [
    ...preferred.filter((row) => presentMainRows.includes(row)),
    ...presentMainRows
      .filter((row) => !preferred.includes(row))
      .sort((a, b) => a.localeCompare(b)),
  ];
  const presentBunkeRows = [
    ...new Set(bunkeCodes.map(({ code }) => ("row" in code ? code.row : ""))),
  ].filter(Boolean);
  const bunkeRowOrder = [
    ...BUNKE_ROWS.filter((row) => presentBunkeRows.includes(row)),
    ...presentBunkeRows
      .filter((row) => !BUNKE_ROWS.includes(row))
      .sort((a, b) => a.localeCompare(b)),
  ];
  const unknown = parsed.filter(({ code }) => code.kind === "unknown");
  const unknownRow = unknown.length ? "?" : "";

  const rowY = new Map<string, number>();
  const rows: SchematicPlan["rows"] = [];
  mainRowOrder.forEach((row, index) => {
    const y = TOP + index * ROW_GAP;
    rowY.set(row, y);
    rows.push({ key: row, y, main: true });
  });
  const bunkeStart =
    TOP + (mainRowOrder.length ? mainRowOrder.length * ROW_GAP + BLOCK_GAP : 0);
  bunkeRowOrder.forEach((row, index) => {
    const y = bunkeStart + index * ROW_GAP;
    rowY.set(row, y);
    rows.push({ key: row, y, main: false });
  });
  if (unknownRow) {
    const y =
      (bunkeRowOrder.length
        ? bunkeStart + bunkeRowOrder.length * ROW_GAP
        : TOP + mainRowOrder.length * ROW_GAP) + BLOCK_GAP;
    rowY.set(unknownRow, y);
    rows.push({ key: unknownRow, y, main: false });
  }

  const markers: SchematicMarker[] = [];
  const push = (
    item: SchematicInput,
    kind: ParsedCode["kind"],
    row: string,
    points: Array<[number, number]>,
  ) => {
    markers.push({
      componentId: item.id,
      code: item.code,
      type: item.type,
      kind,
      row,
      points,
    });
  };
  for (const { item, code } of parsed) {
    if (code.kind === "pile") {
      const x = axisX.get(code.axis) ?? LEFT;
      const y = rowY.get(code.row) ?? TOP;
      push(item, "pile", code.row, [[x, y]]);
    } else if (code.kind === "beam") {
      const x1 = axisX.get(code.axis) ?? LEFT;
      const x2 = axisX.get(code.axisEnd) ?? x1;
      const y = rowY.get(code.row) ?? TOP;
      push(
        item,
        "beam",
        code.row,
        x1 === x2
          ? [[x1 - 9, y], [x1 + 9, y]]
          : [[x1, y], [x2, y]],
      );
    } else if (code.kind === "vertical") {
      const y1 = rowY.get(code.row) ?? TOP;
      const y2 = rowY.get(code.rowEnd) ?? y1;
      const x = axisX.get(code.axis) ?? LEFT;
      push(item, "vertical", code.row, [[x, y1], [x, y2]]);
    } else if (code.kind === "corner") {
      const x = axisX.get(code.axis) ?? LEFT;
      const y = rowY.get(code.row) ?? TOP;
      push(item, "corner", code.row, [[x, y]]);
    } else if (code.kind === "fender") {
      const x1 = axisX.get(code.axis) ?? LEFT;
      const x2 = axisX.get(code.axisEnd) ?? x1;
      const y = rowY.get(code.row) ?? TOP;
      push(item, "fender", code.row, [[x1, y], [x2, y]]);
    } else {
      const y = rowY.get(unknownRow) ?? TOP;
      const x = LEFT + (markers.length % 8) * AXIS_GAP;
      push(item, "unknown", unknownRow, [[x, y]]);
    }
  }

  const width = Math.max(
    LEFT + AXIS_GAP,
    ...axes.map((axis) => axis.x + RIGHT),
    ...markers.flatMap((marker) =>
      marker.points.map(([x]) => x + RIGHT),
    ),
  );
  const height = Math.max(
    TOP + ROW_GAP,
    ...rows.map((row) => row.y + BOTTOM),
  );
  const normalized = markers.map((marker) => ({
    ...marker,
    points: marker.points.map(
      ([x, y]) => [x / width, y / height] as [number, number],
    ),
  }));
  const bunkeRows = rows.filter((row) => !row.main && row.key !== "?");
  const bunke = bunkeRows.length
    ? {
        x0:
          Math.min(...bunkeRows.flatMap((row) =>
            markers
              .filter((marker) => marker.row === row.key)
              .flatMap((marker) => marker.points.map(([x]) => x)),
          )) - 24,
        y0: Math.min(...bunkeRows.map((row) => row.y)) - 22,
        x1:
          Math.max(...bunkeRows.flatMap((row) =>
            markers
              .filter((marker) => marker.row === row.key)
              .flatMap((marker) => marker.points.map(([x]) => x)),
          )) + 24,
        y1: Math.max(...bunkeRows.map((row) => row.y)) + 22,
      }
    : null;

  return {
    key,
    title:
      zone === "Cầu chính" && bunkeCodes.length
        ? `PD${segment} ${zone} + Bunke · Sơ đồ`
        : `PD${segment} ${zone} · Sơ đồ`,
    zone,
    segment,
    width,
    height,
    axes,
    rows,
    bunke,
    markers: normalized,
    bunkeGap,
  };
}
