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
  /** Bunke axes shown as a compact secondary axis row above the block. */
  bunkeAxes: Array<{ value: number; x: number }>;
  rows: Array<{ key: string; y: number; main: boolean }>;
  bunke: { x0: number; y0: number; x1: number; y1: number } | null;
  bunkeBlocks: Array<{
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    axes: Array<{ value: number; x: number }>;
    rows: string[];
  }>;
  markers: SchematicMarker[];
  /** Pile positions with no repair record (hollow squares), plan units. */
  gridPiles: Array<{ x: number; y: number; code: string }>;
  /** Transverse deck beams (dashed), plan units. */
  crossBeams: Array<{ x: number; y0: number; y1: number }>;
};

/**
 * Cầu chính pile grid read from the owner-approved PD2 sketch: rows I/F carry
 * piles on every axis except 50,53,56,…; rows H/G only on 50,53,56,…; Bunke rows
 * E/D/B/A on every Bunke axis (row C has none).
 */
export function hasDeckPile(row: string, axis: number): boolean {
  const onCross = (axis - 50) % 3 === 0;
  if (row === "I" || row === "F") return !onCross;
  if (row === "H" || row === "G") return onCross;
  return ["E", "D", "B", "A"].includes(row);
}

const MAIN_ROWS: Record<string, string[]> = {
  "Cầu chính": ["I", "H", "G", "F"],
  "Cầu dẫn": ["N", "O", "P", "Q", "M"],
};
const BUNKE_ROWS = ["E", "D", "C", "B", "A"];
const BUNKE_ROW_SET = new Set(BUNKE_ROWS);

const LEFT = 66;
const TOP = 70;
export const SCHEMATIC_AXIS_GAP = 30;
const AXIS_GAP = SCHEMATIC_AXIS_GAP;
const ROW_GAP = 64;
const BUNKE_ROW_GAP = 46;
const BLOCK_GAP = 30;
const RIGHT = 44;
const BOTTOM = 56;

/**
 * Owner-approved PD2 sketch (Mat_bang_PD2_va_bunke_phat_sinh_26-11): each Bunke
 * axis sits under a fractional main-deck axis. Approximate by design.
 */
const BUNKE_ATTACHMENTS: Record<
  string,
  Array<{ axes: number[]; anchors: number[] }>
> = {
  "Cầu chính": [
    { axes: [152], anchors: [49.75] },
    { axes: [153, 154, 155], anchors: [64.3, 66.9, 69.6] },
    { axes: [156, 157, 158], anchors: [77.1, 79.7, 82.3] },
  ],
};

export const SCHEMATIC_BOUNDS = {
  minX: 0,
  minY: 0,
  maxX: 1,
  maxY: 1,
};

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
  const usedMainAxes = [
    ...new Set(mainCodes.flatMap(({ code }) => axisOf(code))),
  ].sort((a, b) => a - b);
  // Continuous, evenly spaced axes like the drawings (no gap compression).
  const mainAxes = usedMainAxes.length
    ? Array.from(
        { length: usedMainAxes[usedMainAxes.length - 1] - usedMainAxes[0] + 1 },
        (_, index) => usedMainAxes[0] + index,
      )
    : [];
  const presentBunkeAxes = bunkeCodes.flatMap(({ code }) => axisOf(code));
  // Show every Bunke axis of the attached blocks (e.g. 158) once any is used.
  const attachmentAxes = (BUNKE_ATTACHMENTS[zone] ?? [])
    .filter((group) => group.axes.some((axis) => presentBunkeAxes.includes(axis)))
    .flatMap((group) => group.axes);
  const bunkeAxes = [...new Set([...presentBunkeAxes, ...attachmentAxes])].sort(
    (a, b) => a - b,
  );
  const mainAxisX = new Map(mainAxes.map((axis, index) => [axis, LEFT + index * AXIS_GAP]));
  const axes = mainAxes.map((value) => ({
    value,
    x: mainAxisX.get(value) ?? LEFT,
  }));

  function mainXFor(axis: number): number {
    const exact = mainAxisX.get(axis);
    if (exact !== undefined) return exact;
    if (!mainAxes.length) return LEFT;
    const lower =
      [...mainAxes].reverse().find((value) => value <= axis) ?? mainAxes[0];
    const upper =
      mainAxes.find((value) => value >= axis) ?? mainAxes[mainAxes.length - 1];
    const lowerX = mainAxisX.get(lower) ?? LEFT;
    const upperX = mainAxisX.get(upper) ?? lowerX;
    if (lower === upper) return lowerX;
    const ratio = (axis - lower) / (upper - lower);
    return lowerX + ratio * (upperX - lowerX);
  }

  function bunkeXFor(axis: number): number {
    const attachment = BUNKE_ATTACHMENTS[zone]?.find((group) =>
      group.axes.includes(axis),
    );
    if (attachment) {
      const index = attachment.axes.indexOf(axis);
      return mainXFor(
        attachment.anchors[Math.min(index, attachment.anchors.length - 1)],
      );
    }
    if (mainAxisX.has(axis)) return mainAxisX.get(axis) ?? LEFT;
    // Unknown Bunke axes stay under the right end of the main grid, never in
    // a separate block to the right.
    if (mainAxes.length) {
      const index = bunkeAxes.indexOf(axis);
      const span = Math.min(bunkeAxes.length, mainAxes.length);
      const anchorIndex = Math.max(0, mainAxes.length - span + index);
      return LEFT + Math.min(anchorIndex, mainAxes.length - 1) * AXIS_GAP;
    }
    return LEFT + bunkeAxes.indexOf(axis) * AXIS_GAP;
  }

  const bunkeAxisPositions = bunkeAxes.map((value) => ({
    value,
    x: bunkeXFor(value),
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
    // Keep the full E..A ladder (row C has no piles but is part of the frame).
    ...(presentBunkeRows.some((row) => BUNKE_ROW_SET.has(row)) ? BUNKE_ROWS : []),
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
    const y = bunkeStart + index * BUNKE_ROW_GAP;
    rowY.set(row, y);
    rows.push({ key: row, y, main: false });
  });
  if (unknownRow) {
    const y =
      (bunkeRowOrder.length
        ? bunkeStart + bunkeRowOrder.length * BUNKE_ROW_GAP
        : TOP + mainRowOrder.length * ROW_GAP) + BLOCK_GAP;
    rowY.set(unknownRow, y);
    rows.push({ key: unknownRow, y, main: false });
  }

  const rowKeysForCode = (code: ParsedCode): string[] =>
    code.kind === "vertical" ? [code.row, code.rowEnd] : "row" in code ? [code.row] : [];

  const bunkeBlocks: SchematicPlan["bunkeBlocks"] = [];
  const coveredBunkeAxes = new Set<number>();
  const addBunkeBlock = (axes: number[], groupItems: typeof bunkeCodes) => {
    if (!axes.length || !groupItems.length) return;
    const positions = axes.map((value) => ({ value, x: bunkeXFor(value) }));
    const rowKeys = bunkeRowOrder.filter((row) => rowY.has(row));
    if (!rowKeys.length) return;
    axes.forEach((axis) => coveredBunkeAxes.add(axis));
    bunkeBlocks.push({
      x0: Math.min(...positions.map((axis) => axis.x)) - 22,
      y0: Math.min(...rowKeys.map((row) => rowY.get(row) ?? TOP)) - 22,
      x1: Math.max(...positions.map((axis) => axis.x)) + 22,
      y1: Math.max(...rowKeys.map((row) => rowY.get(row) ?? TOP)) + 18,
      axes: positions,
      rows: rowKeys,
    });
  };
  for (const group of BUNKE_ATTACHMENTS[zone] ?? []) {
    const axes = group.axes.filter((axis) => bunkeAxes.includes(axis));
    const groupItems = bunkeCodes.filter(({ code }) =>
      axisOf(code).some((axis) => group.axes.includes(axis)),
    );
    addBunkeBlock(axes, groupItems);
  }
  const looseAxes = bunkeAxes.filter((axis) => !coveredBunkeAxes.has(axis));
  addBunkeBlock(
    looseAxes,
    bunkeCodes.filter(({ code }) =>
      axisOf(code).some((axis) => looseAxes.includes(axis)),
    ),
  );

  const markers: SchematicMarker[] = [];
  const bunkeIds = new Set(bunkeCodes.map(({ item }) => item.id));
  const axisXFor = (item: SchematicInput, axis: number) =>
    bunkeIds.has(item.id)
      ? bunkeXFor(axis)
      : mainAxisX.get(axis) ?? mainXFor(axis);
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
      const x = axisXFor(item, code.axis);
      const y = rowY.get(code.row) ?? TOP;
      push(item, "pile", code.row, [[x, y]]);
    } else if (code.kind === "beam") {
      const x1 = axisXFor(item, code.axis);
      const x2 = axisXFor(item, code.axisEnd);
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
      const x = axisXFor(item, code.axis);
      push(item, "vertical", code.row, [[x, y1], [x, y2]]);
    } else if (code.kind === "corner") {
      const x = axisXFor(item, code.axis);
      const y = rowY.get(code.row) ?? TOP;
      push(item, "corner", code.row, [[x, y]]);
    } else if (code.kind === "fender") {
      const x1 = axisXFor(item, code.axis);
      const x2 = axisXFor(item, code.axisEnd);
      const y = rowY.get(code.row) ?? TOP;
      push(item, "fender", code.row, [[x1, y], [x2, y]]);
    } else {
      const y = rowY.get(unknownRow) ?? TOP;
      const x = LEFT + (markers.length % 8) * AXIS_GAP;
      push(item, "unknown", unknownRow, [[x, y]]);
    }
  }

  // Full deck: hollow squares for piles without a repair record + cross beams.
  const gridPiles: SchematicPlan["gridPiles"] = [];
  const crossBeams: SchematicPlan["crossBeams"] = [];
  if (zone === "Cầu chính") {
    const occupied = new Set(
      parsed.flatMap(({ code }) =>
        code.kind === "pile" ? [`${code.row}${code.axis}`] : [],
      ),
    );
    for (const row of mainRowOrder) {
      for (const axis of mainAxes) {
        if (hasDeckPile(row, axis) && !occupied.has(`${row}${axis}`)) {
          gridPiles.push({ x: mainAxisX.get(axis) ?? LEFT, y: rowY.get(row) ?? TOP, code: `${row}${axis}` });
        }
      }
    }
    for (const row of bunkeRowOrder) {
      for (const axis of bunkeAxes) {
        if (hasDeckPile(row, axis) && !occupied.has(`${row}${axis}`)) {
          gridPiles.push({ x: bunkeXFor(axis), y: rowY.get(row) ?? TOP, code: `${row}${axis}` });
        }
      }
    }
    const mainYs = mainRowOrder.map((row) => rowY.get(row) ?? TOP);
    if (mainYs.length > 1) {
      for (const axis of mainAxes) {
        if ((axis - 50) % 3 === 0) {
          crossBeams.push({
            x: mainAxisX.get(axis) ?? LEFT,
            y0: Math.min(...mainYs),
            y1: Math.max(...mainYs),
          });
        }
      }
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
    // room for the Bunke axis numbers drawn under each block
    ...bunkeBlocks.map((block) => block.y1 + 30),
  );
  const normalized = markers.map((marker) => ({
    ...marker,
    points: marker.points.map(
      ([x, y]) => [x / width, y / height] as [number, number],
    ),
  }));
  const bunke =
    bunkeBlocks.length
      ? {
          x0: Math.min(...bunkeBlocks.map((block) => block.x0)),
          y0: Math.min(...bunkeBlocks.map((block) => block.y0)),
          x1: Math.max(...bunkeBlocks.map((block) => block.x1)),
          y1: Math.max(...bunkeBlocks.map((block) => block.y1)),
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
    bunkeAxes: bunkeAxisPositions,
    rows,
    bunke,
    bunkeBlocks,
    markers: normalized,
    gridPiles,
    crossBeams,
  };
}
