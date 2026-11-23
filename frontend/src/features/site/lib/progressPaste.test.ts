import { describe, expect, it } from "vitest";
import {
  applyPasteAnswers,
  buildZaloSummary,
  dailyProgressErrorMessage,
  groupPasteQuestions,
  pasteIdempotencyKey,
  type PasteParse,
} from "./progressPaste";

const PILE_STAGE = "stage-pile";
const BEAM_STAGE = "stage-beam";

function pileLine(codes: string[]) {
  return {
    work_text: "Cọc đục",
    component_type: "pile",
    stage_candidates: [
      { stage_definition_id: PILE_STAGE, name: "Đục", component_type: "pile" },
    ],
    items: codes.map((code) => ({
      raw: code,
      code,
      component_id: `cmp-${code}`,
      zone: "Cầu chính",
      segment: 2,
      status_guess: "COMPLETED" as const,
      stage_definition_id: PILE_STAGE,
    })),
  };
}

/** Parsed representation of the 22/11 golden Zalo message. */
function goldenParse(): PasteParse {
  const beamCodes = ["F-66-67", "A-B-153", "B-D-153"];
  return {
    event_date: "2026-11-22",
    date_source: "text",
    batch_id: "batch-1",
    lines: [
      pileLine(["I49", "I51", "I55", "I57", "I58", "I60", "I63", "I64", "I67"]),
      pileLine(["H65", "H62", "H53", "H50"]),
      pileLine(["G50", "G65", "G65"]),
      pileLine(["F54", "F55", "F57", "F64", "F67", "F69"]),
      pileLine(["A155"]),
      pileLine(["B153", "B155"]),
      pileLine(["E153", "E155"]),
      {
        work_text: "Dầm đục",
        component_type: "beam",
        stage_candidates: [
          { stage_definition_id: BEAM_STAGE, name: "Đục", component_type: "beam" },
        ],
        items: beamCodes.map((code) => ({
          raw: code,
          code,
          component_id: `cmp-${code}`,
          zone: "Bunke",
          segment: 1,
          status_guess: "COMPLETED" as const,
          stage_definition_id: BEAM_STAGE,
        })),
      },
    ],
    questions: [
      {
        id: "duplicate:G65",
        kind: "duplicate_code",
        message_vi: "Mã G65 xuất hiện 2 lần.",
        options: [
          { label_vi: "Bỏ trùng", value: "dedupe" },
          { label_vi: "Mã khác", value: "replace_code" },
        ],
      },
      {
        id: "completed:cmp-F-66-67:evt-old",
        kind: "completed_earlier",
        message_vi: "F-66-67 đã hoàn thành ngày trước.",
        codes: ["F-66-67"],
        apply: {
          action: "correct_earlier_to_in_progress",
          event_ids: ["evt-old", "evt-older"],
        },
        options: [
          { label_vi: "Ghi thêm hoàn thành", value: "add_completed" },
          { label_vi: "Ngày trước là đang làm", value: "previous_was_in_progress" },
          { label_vi: "Bỏ qua", value: "skip" },
        ],
      },
      {
        id: "outside:Bunke:1:beam",
        kind: "outside_scope",
        message_vi: "3 dầm Bunke ngoài phạm vi. Thi công cùng đợt?",
        codes: beamCodes,
        options: [
          { label_vi: "Thi công cùng đợt", value: "include" },
          { label_vi: "Bỏ qua", value: "skip" },
        ],
      },
    ],
    warnings: [],
  };
}

const GOLDEN_ANSWERS = {
  "duplicate:G65": "dedupe",
  "completed:cmp-F-66-67:evt-old": "previous_was_in_progress",
  "outside:Bunke:1:beam": "include",
};

describe("progress paste apply", () => {
  it("maps the 22/11 golden message to a daily payload, batch additions and one correction", () => {
    const result = applyPasteAnswers(goldenParse(), GOLDEN_ANSWERS, {}, "2026-11-22");
    expect(result.errors).toEqual([]);
    expect(result.payload.event_date).toBe("2026-11-22");
    expect(result.payload.lines).toHaveLength(8);
    expect(result.payload.lines.slice(0, 7).map((line) => line.component_ids.length)).toEqual([
      9, 4, 2, 6, 1, 2, 2,
    ]);
    expect(result.payload.lines.every((line) => line.status === "COMPLETED")).toBe(true);
    expect(result.payload.lines[0].stage_definition_id).toBe(PILE_STAGE);
    expect(result.payload.lines[7]).toEqual({
      stage_definition_id: BEAM_STAGE,
      component_ids: ["cmp-F-66-67", "cmp-A-B-153", "cmp-B-D-153"],
      status: "COMPLETED",
    });
    expect(result.savedLines[2].codes).toEqual(["G50", "G65"]);
    expect(result.batch_component_ids).toEqual([
      "cmp-F-66-67", "cmp-A-B-153", "cmp-B-D-153",
    ]);
    expect(result.corrections).toEqual([
      {
        event_id: "evt-old",
        reason: "Theo tin nhắn ngày 22/11/2026: hôm trước đang làm",
      },
      {
        event_id: "evt-older",
        reason: "Theo tin nhắn ngày 22/11/2026: hôm trước đang làm",
      },
    ]);
  });

  it("refuses to apply while any question is unanswered", () => {
    const result = applyPasteAnswers(goldenParse(), {}, {}, "2026-11-22");
    expect(result.payload.lines).toEqual([]);
    expect(result.errors.some((error) => error.startsWith("Chưa trả lời"))).toBe(true);
  });

  it("skips unknown codes and blocks replace_code until the message is fixed", () => {
    const parsed = goldenParse();
    parsed.questions = [
      {
        id: "unknown:Z999",
        kind: "unknown_code",
        message_vi: "Không tìm thấy Z999.",
        options: [
          { label_vi: "Bỏ qua", value: "skip" },
          { label_vi: "Mã khác", value: "replace_code" },
        ],
      },
    ];
    const skipped = applyPasteAnswers(
      parsed,
      { "unknown:Z999": "skip" },
      {},
      "2026-11-22",
    );
    expect(skipped.errors).toEqual([]);
    expect(skipped.skipped_codes).toEqual(["Z999"]);
    const replace = applyPasteAnswers(
      parsed,
      { "unknown:Z999": "replace_code" },
      {},
      "2026-11-22",
    );
    expect(replace.errors.some((error) => error.includes("Z999"))).toBe(true);
  });

  it("uses a manual stage when the parser has no candidate", () => {
    const parsed: PasteParse = {
      event_date: "2026-11-22",
      lines: [{
        work_text: "Công tác lạ",
        component_type: "pile",
        stage_candidates: [],
        items: [{ raw: "F67", code: "F67", component_id: "c1", status_guess: "COMPLETED" }],
      }],
      questions: [],
    };
    const missing = applyPasteAnswers(parsed, {}, {}, "2026-11-22");
    expect(missing.errors.length).toBe(1);
    const manual = applyPasteAnswers(parsed, {}, { 0: PILE_STAGE }, "2026-11-22");
    expect(manual.errors).toEqual([]);
    expect(manual.payload.lines[0].stage_definition_id).toBe(PILE_STAGE);
  });

  it("applies the status confirmation question", () => {
    const parsed = goldenParse();
    parsed.lines = [parsed.lines[0]];
    parsed.questions = [{
      id: "status:in_progress",
      kind: "status_confirm",
      message_vi: "Xác nhận trạng thái",
      options: [
        { label_vi: "Hoàn thành", value: "COMPLETED" },
        { label_vi: "Đang thi công", value: "IN_PROGRESS" },
      ],
    }];
    const result = applyPasteAnswers(
      parsed,
      { "status:in_progress": "IN_PROGRESS" },
      {},
      "2026-11-22",
    );
    expect(result.payload.lines[0].status).toBe("IN_PROGRESS");
  });
});

describe("idempotency and Zalo summary", () => {
  it("derives a stable key from text and date", () => {
    const first = pasteIdempotencyKey("Cọc đục ngày 22/11", "2026-11-22");
    expect(first).toBe(pasteIdempotencyKey("Cọc đục ngày 22/11", "2026-11-22"));
    expect(first).not.toBe(pasteIdempotencyKey("Cọc đục ngày 23/11", "2026-11-22"));
    expect(first).toMatch(/^paste-2026-11-22-[0-9a-f]{8}$/);
  });

  it("formats counts, grouped codes and pending acceptance", () => {
    const result = applyPasteAnswers(goldenParse(), GOLDEN_ANSWERS, {}, "2026-11-22");
    const text = buildZaloSummary({
      eventDate: "2026-11-22",
      lines: result.savedLines,
      pendingAcceptance: 5,
    });
    expect(text).toContain("Ngày 22/11/2026");
    expect(text).toContain("Tổng: 26 cọc · 3 dầm");
    expect(text).toContain("G50, G65");
    expect(text).toContain("F-66-67, A-B-153, B-D-153");
    expect(text).toContain("Chưa nghiệm thu: 5 cấu kiện đã xong");
  });
});

describe("daily progress errors and question labels", () => {
  it("turns a FastAPI future-date 422 into a Vietnamese message", () => {
    const error = new Error(
      JSON.stringify({
        detail: [
          {
            type: "value_error",
            loc: ["body", "event_date"],
            msg: "Value error, event_date must not be in the future",
          },
        ],
      }),
    );
    expect(dailyProgressErrorMessage(error)).toBe(
      "Ngày thi công không được ở tương lai. Chọn hôm nay hoặc ngày trước đó.",
    );
  });

  it("keeps an unknown backend message visible", () => {
    expect(dailyProgressErrorMessage(new Error("Máy chủ đang bận"))).toBe(
      "Máy chủ đang bận",
    );
  });

  it("labels a future_date question for the generic card", () => {
    const [group] = groupPasteQuestions([
      {
        id: "future-date:1",
        kind: "future_date",
        message_vi: "Ngày trong tương lai",
        options: [{ label_vi: "Dùng hôm nay", value: "today" }],
      },
    ]);
    expect(group.label).toBe("Ngày trong tương lai");
    expect(group.questions).toHaveLength(1);
  });
});
