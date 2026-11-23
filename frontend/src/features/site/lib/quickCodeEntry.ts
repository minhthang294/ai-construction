export type QuickCodeRow = {
  id: string;
  canonical_code: string;
  raw_code?: string;
};

export type ParsedQuickCodes = {
  codes: string[];
  duplicates: string[];
};

const SIMPLE_CODE = /^([A-Za-z]+)(\d+)$/;

/**
 * Expand shorthand written on site into concrete component codes.
 *
 * A bare number reuses the last simple letter prefix: "F67,64" -> F67, F64.
 * Codes that contain a hyphen (beam codes such as I-40-42 / I40-42) are kept
 * as typed. Duplicates are removed in input order.
 */
export function parseQuickCodes(input: string): ParsedQuickCodes {
  const tokens = input
    .split(/[\s,;]+/)
    .map((token) => token.trim())
    .filter(Boolean);
  const codes: string[] = [];
  const duplicates: string[] = [];
  const seen = new Set<string>();
  let prefix = "";

  for (const token of tokens) {
    let code: string;
    if (/^\d+$/.test(token)) {
      code = prefix ? `${prefix}${token}` : token;
    } else {
      code = token.toUpperCase();
      const simple = SIMPLE_CODE.exec(code);
      if (simple) prefix = simple[1];
    }
    if (seen.has(code)) {
      duplicates.push(code);
      continue;
    }
    seen.add(code);
    codes.push(code);
  }
  return { codes, duplicates };
}

export type QuickCodeAnalysis = {
  codes: string[];
  matched: Array<{ code: string; row: QuickCodeRow }>;
  matchedIds: string[];
  unknown: string[];
  duplicates: string[];
};

/**
 * Match parsed codes against the components currently in scope.
 *
 * Canonical codes win over raw codes. A row that is already selected, or that
 * is reached by a second code, is reported as a duplicate instead of appearing
 * twice.
 */
export function analyzeQuickCodes(
  input: string,
  rows: QuickCodeRow[],
  existingIds: string[] = [],
): QuickCodeAnalysis {
  const parsed = parseQuickCodes(input);
  const byCode = new Map<string, QuickCodeRow>();
  for (const row of rows) {
    byCode.set(row.canonical_code.toUpperCase(), row);
  }
  for (const row of rows) {
    if (!row.raw_code) continue;
    const key = row.raw_code.toUpperCase();
    if (!byCode.has(key)) byCode.set(key, row);
  }

  const existing = new Set(existingIds);
  const usedIds = new Set<string>();
  const matched: QuickCodeAnalysis["matched"] = [];
  const unknown: string[] = [];
  const duplicates = [...parsed.duplicates];

  for (const code of parsed.codes) {
    const row = byCode.get(code);
    if (!row) {
      unknown.push(code);
      continue;
    }
    if (existing.has(row.id) || usedIds.has(row.id)) {
      duplicates.push(code);
      continue;
    }
    usedIds.add(row.id);
    matched.push({ code, row });
  }

  return {
    codes: parsed.codes,
    matched,
    matchedIds: matched.map((item) => item.row.id),
    unknown,
    duplicates,
  };
}
