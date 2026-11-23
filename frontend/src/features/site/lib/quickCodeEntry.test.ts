import { describe, expect, it } from "vitest";
import { analyzeQuickCodes, parseQuickCodes } from "./quickCodeEntry";

describe("quick code entry parser", () => {
  it("expands bare numbers with the last letter prefix from the site example", () => {
    const parsed = parseQuickCodes("F67,64,57,55, G65,62, H65 B153 155");
    expect(parsed.codes).toEqual([
      "F67", "F64", "F57", "F55", "G65", "G62", "H65", "B153", "B155",
    ]);
    expect(parsed.duplicates).toEqual([]);
  });

  it("keeps beam codes with hyphens unchanged and accepts lowercase", () => {
    expect(parseQuickCodes("i-40-42, I40-42").codes).toEqual(["I-40-42", "I40-42"]);
  });

  it("removes duplicates in input order and ignores separators", () => {
    const parsed = parseQuickCodes("F67, f67;\n64  F64");
    expect(parsed.codes).toEqual(["F67", "F64"]);
    expect(parsed.duplicates).toEqual(["F67", "F64"]);
  });

  it("leaves a leading bare number alone when no prefix was seen", () => {
    expect(parseQuickCodes("64 F67 55").codes).toEqual(["64", "F67", "F55"]);
  });
});

describe("quick code entry matching", () => {
  const rows = [
    { id: "1", canonical_code: "F67", raw_code: "F67" },
    { id: "2", canonical_code: "F64", raw_code: "F64" },
    { id: "3", canonical_code: "I-40-42", raw_code: "I40-42" },
  ];

  it("matches within the provided rows and keeps input order", () => {
    const result = analyzeQuickCodes("F64 F67", rows);
    expect(result.matched.map((item) => item.code)).toEqual(["F64", "F67"]);
    expect(result.matchedIds).toEqual(["2", "1"]);
    expect(result.unknown).toEqual([]);
  });

  it("accepts the raw beam code spelling", () => {
    const result = analyzeQuickCodes("I40-42", rows);
    expect(result.matchedIds).toEqual(["3"]);
    expect(result.matched[0].code).toBe("I40-42");
  });

  it("reports unknown codes and already selected rows without matching them twice", () => {
    const result = analyzeQuickCodes("F67 64 Z99 I-40-42 I40-42", rows, ["1", "3"]);
    expect(result.unknown).toEqual(["Z99"]);
    expect(result.matchedIds).toEqual(["2"]);
    expect(result.duplicates).toEqual(["F67", "I-40-42", "I40-42"]);
  });
});
