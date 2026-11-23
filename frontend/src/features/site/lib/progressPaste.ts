/**
 * Pure helpers for the "Dán tin nhắn" field flow: apply parse answers to a
 * daily-preview payload, derive corrections/batch additions, and format the
 * Zalo summary. No network or storage access here.
 */

import type { DailyProgressPayload } from "./dailyProgress";

export type PasteStageCandidate = {
  stage_definition_id: string;
  name: string;
  component_type: string;
};

export type PasteEarlierEvent = {
  event_id: string;
  event_date: string;
  status: string;
};

export type PasteItem = {
  raw: string;
  code: string;
  component_id?: string | null;
  zone?: string | null;
  segment?: number | null;
  status_guess?: "COMPLETED" | "IN_PROGRESS";
  stage_definition_id?: string | null;
  stage_candidates?: PasteStageCandidate[];
  earlier_events?: PasteEarlierEvent[];
  in_batch?: boolean;
};

export type PasteLine = {
  work_text: string;
  stage_candidates?: PasteStageCandidate[];
  component_type: string;
  items: PasteItem[];
};

export type PasteQuestionOption = { label_vi: string; value: string };

export type PasteQuestion = {
  id: string;
  kind: string;
  message_vi: string;
  options: PasteQuestionOption[];
  codes?: string[];
  apply?: Record<string, unknown>;
};

export type PasteQuestionGroup = {
  kind: string;
  label: string;
  questions: PasteQuestion[];
  commonOptions: PasteQuestionOption[];
};

const QUESTION_LABELS: Record<string, string> = {
  multiple_stage: "Chọn công đoạn",
  stage: "Chọn công đoạn",
  completed_earlier: "Cấu kiện đã hoàn thành trước đó",
  duplicate_code: "Mã trùng trong tin nhắn",
  unknown_code: "Mã không tìm thấy",
  outside_scope: "Cấu kiện ngoài phạm vi",
  status_confirm: "Xác nhận trạng thái",
  future_date: "Ngày trong tương lai",
};

export function groupPasteQuestions(questions: PasteQuestion[]): PasteQuestionGroup[] {
  const groups = new Map<string, PasteQuestion[]>();
  for (const question of questions) {
    groups.set(question.kind, [...(groups.get(question.kind) ?? []), question]);
  }
  return [...groups.entries()].map(([kind, items]) => {
    const values = items.map(
      (question) => new Set(question.options.map((option) => option.value)),
    );
    const commonOptions = items[0].options.filter((option) =>
      values.every((set) => set.has(option.value)),
    );
    return {
      kind,
      label: QUESTION_LABELS[kind] ?? kind,
      questions: items,
      commonOptions,
    };
  });
}

export type PasteParse = {
  event_date?: string | null;
  date_source?: string | null;
  batch_id?: string | null;
  lines: PasteLine[];
  questions: PasteQuestion[];
  unknown_codes?: string[];
  warnings?: string[];
};

export type PasteAnswers = Record<string, string>;
export type PasteManualStages = Record<number, string>;

export type PasteAppliedLine = {
  work_text: string;
  stage_display_name?: string | null;
  component_type: string;
  stage_definition_id: string;
  status: "COMPLETED" | "IN_PROGRESS";
  component_ids: string[];
  codes: string[];
};

export type PasteApplyResult = {
  payload: DailyProgressPayload;
  savedLines: PasteAppliedLine[];
  corrections: Array<{ event_id: string; reason: string }>;
  batch_component_ids: string[];
  skipped_codes: string[];
  errors: string[];
};

const PILE_NOUN = "cọc";
const BEAM_NOUN = "dầm";

export function formatPasteDate(value: string | null | undefined): string {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}

const DAILY_ERROR_TRANSLATIONS: Array<[RegExp, string]> = [
  [
    /event_date must not be in the future/i,
    "Ngày thi công không được ở tương lai. Chọn hôm nay hoặc ngày trước đó.",
  ],
  [
    /a daily entry supports at most (\d+) components/i,
    "Một lần ghi tối đa $1 cấu kiện.",
  ],
  [/Input should be a valid date/i, "Ngày thi công không hợp lệ."],
];

function translateDailyMessage(message: string): string {
  const cleaned = message.replace(/^Value error,\s*/i, "").trim();
  for (const [pattern, replacement] of DAILY_ERROR_TRANSLATIONS) {
    if (pattern.test(cleaned)) return cleaned.replace(pattern, replacement);
  }
  return cleaned;
}

/** Turn FastAPI 422/409 text into a visible Vietnamese reason for the action. */
export function dailyProgressErrorMessage(cause: unknown): string {
  const message = cause instanceof Error ? cause.message.trim() : "";
  if (!message) return "Không gửi được dữ liệu tiến độ. Thử lại.";
  try {
    const body = JSON.parse(message);
    const detail = body?.detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => String(item?.msg ?? ""))
        .filter(Boolean);
      if (messages.length) return messages.map(translateDailyMessage).join(" ");
    }
  } catch {
    // Plain text from a 409/500 or a network error.
  }
  return translateDailyMessage(message);
}

function applyIds(question: PasteQuestion): string[] {
  const value = question.apply?.component_ids;
  return Array.isArray(value) ? value.map(String) : [];
}

function applyEventIds(question: PasteQuestion): string[] {
  const value = question.apply?.event_ids;
  return Array.isArray(value) ? value.map(String) : [];
}

function outsideComponents(question: PasteQuestion, parsed: PasteParse): string[] {
  const explicit = applyIds(question);
  if (explicit.length) return explicit;
  const codes = new Set((question.codes ?? []).map((code) => code.toUpperCase()));
  const parts = question.id.split(":");
  const zone = parts[0] === "outside" ? parts[1] : null;
  const segment = parts[0] === "outside" ? Number(parts[2]) : null;
  const type = parts[0] === "outside" ? parts[3] : null;
  const ids: string[] = [];
  for (const line of parsed.lines) {
    for (const item of line.items) {
      if (!item.component_id) continue;
      if (codes.size && codes.has(item.code.toUpperCase())) ids.push(item.component_id);
      else if (
        zone &&
        item.zone === zone &&
        item.segment === segment &&
        (!type || line.component_type === type)
      ) {
        ids.push(item.component_id);
      }
    }
  }
  return ids;
}

/**
 * Apply every answer locally. Unanswered or contradictory questions return
 * errors and an empty payload, so the caller cannot save by accident.
 */
export function applyPasteAnswers(
  parsed: PasteParse,
  answers: PasteAnswers,
  manualStages: PasteManualStages,
  eventDate: string,
): PasteApplyResult {
  const errors: string[] = [];
  const skippedIds = new Set<string>();
  const skippedCodes = new Set<string>();
  const stageChoices: Record<string, string> = {};
  const corrections: Array<{ event_id: string; reason: string }> = [];
  const batchIds: string[] = [];
  let statusOverride: "COMPLETED" | "IN_PROGRESS" | null = null;

  for (const question of parsed.questions) {
    const answer = answers[question.id];
    if (!answer) {
      errors.push(`Chưa trả lời: ${question.message_vi}`);
      continue;
    }
    if (question.kind === "status_confirm") {
      if (answer === "COMPLETED" || answer === "IN_PROGRESS") statusOverride = answer;
      continue;
    }
    if (question.kind === "stage" || question.id.startsWith("stage:")) {
      const componentId =
        (question.apply?.component_id as string | undefined) ??
        question.id.split(":")[1];
      if (componentId) stageChoices[componentId] = answer;
      continue;
    }
    if (question.kind === "duplicate_code" || question.id.startsWith("duplicate:")) {
      if (answer === "replace_code") {
        errors.push("Mã trùng cần được sửa trong tin nhắn rồi dán lại.");
      }
      continue;
    }
    if (question.kind === "unknown_code" || question.id.startsWith("unknown:")) {
      const code = question.codes?.[0] ?? question.id.split(":")[1] ?? "";
      if (answer === "replace_code") {
        errors.push(`Mã ${code} cần được sửa trong tin nhắn rồi dán lại.`);
      } else if (code) {
        skippedCodes.add(code.toUpperCase());
      }
      continue;
    }
    if (question.kind === "completed_earlier" || question.id.startsWith("completed:")) {
      const parts = question.id.split(":");
      const componentId =
        (question.apply?.component_id as string | undefined) ?? parts[1];
      const eventId =
        applyEventIds(question)[0] ??
        (question.apply?.event_id as string | undefined) ??
        parts[2];
      if (answer === "skip") {
        if (componentId) skippedIds.add(componentId);
      } else if (answer === "previous_was_in_progress") {
        const ids = applyEventIds(question);
        if (ids.length) {
          for (const eventId of ids) {
            if (!corrections.some((item) => item.event_id === eventId)) {
              corrections.push({
                event_id: eventId,
                reason: `Theo tin nhắn ngày ${formatPasteDate(eventDate)}: hôm trước đang làm`,
              });
            }
          }
        } else if (eventId) {
          corrections.push({
            event_id: eventId,
            reason: `Theo tin nhắn ngày ${formatPasteDate(eventDate)}: hôm trước đang làm`,
          });
        }
      }
      continue;
    }
    if (question.kind === "outside_scope" || question.id.startsWith("outside:")) {
      const ids = outsideComponents(question, parsed);
      if (answer === "include") {
        for (const id of ids) if (!batchIds.includes(id)) batchIds.push(id);
      } else {
        for (const id of ids) skippedIds.add(id);
      }
    }
  }

  const payloadLines: DailyProgressPayload["lines"] = [];
  const savedLines: PasteAppliedLine[] = [];

  parsed.lines.forEach((line, lineIndex) => {
    const grouped = new Map<
      string,
      { stage: string; status: "COMPLETED" | "IN_PROGRESS"; ids: string[]; codes: string[] }
    >();
    const seen = new Set<string>();
    for (const item of line.items) {
      if (!item.component_id || skippedIds.has(item.component_id)) continue;
      const upperCode = item.code.toUpperCase();
      if (skippedCodes.has(upperCode)) continue;
      if (seen.has(item.component_id)) continue;
      seen.add(item.component_id);
      const status = statusOverride ?? item.status_guess ?? "COMPLETED";
      const stage =
        stageChoices[item.component_id] ||
        manualStages[lineIndex] ||
        item.stage_definition_id ||
        (line.stage_candidates?.length === 1
          ? line.stage_candidates[0].stage_definition_id
          : "") ||
        "";
      if (!stage) {
        errors.push(
          `Chọn công đoạn cho dòng “${line.work_text}” hoặc cấu kiện ${item.code}.`,
        );
        continue;
      }
      const key = `${stage}|${status}`;
      const entry =
        grouped.get(key) ??
        { stage, status, ids: [] as string[], codes: [] as string[] };
      entry.ids.push(item.component_id);
      entry.codes.push(item.code);
      grouped.set(key, entry);
    }
    for (const entry of grouped.values()) {
      payloadLines.push({
        stage_definition_id: entry.stage,
        component_ids: entry.ids,
        status: entry.status,
      });
      savedLines.push({
        work_text: line.work_text,
        component_type: line.component_type,
        stage_definition_id: entry.stage,
        status: entry.status,
        component_ids: entry.ids,
        codes: entry.codes,
      });
    }
  });

  if (!payloadLines.length && !errors.length) {
    errors.push("Không còn cấu kiện nào để ghi sau khi áp dụng câu trả lời.");
  }

  if (errors.length) {
    return {
      payload: { event_date: eventDate, lines: [] },
      savedLines: [],
      corrections: [],
      batch_component_ids: [],
      skipped_codes: [...skippedCodes],
      errors,
    };
  }

  return {
    payload: { event_date: eventDate, lines: payloadLines },
    savedLines,
    corrections,
    batch_component_ids: batchIds,
    skipped_codes: [...skippedCodes],
    errors,
  };
}

/** Stable idempotency key derived from the pasted text and event date. */
export function pasteIdempotencyKey(text: string, eventDate: string): string {
  let hash = 0x811c9dc5;
  const input = `${eventDate}\n${text.trim()}`;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return `paste-${eventDate}-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

export function buildZaloSummary({
  eventDate,
  lines,
  pendingAcceptance,
}: {
  eventDate: string;
  lines: PasteAppliedLine[];
  pendingAcceptance: number;
}): string {
  const pileCount = lines
    .filter((line) => line.component_type === "pile")
    .reduce((sum, line) => sum + line.codes.length, 0);
  const beamCount = lines
    .filter((line) => line.component_type === "beam")
    .reduce((sum, line) => sum + line.codes.length, 0);
  const parts = [`Ngày ${formatPasteDate(eventDate)}`];
  const totals = [
    pileCount ? `${pileCount} ${PILE_NOUN}` : null,
    beamCount ? `${beamCount} ${BEAM_NOUN}` : null,
  ].filter(Boolean);
  if (totals.length) parts.push(`Tổng: ${totals.join(" · ")}`);
  for (const line of lines) {
    const noun = line.component_type === "beam" ? BEAM_NOUN : PILE_NOUN;
    parts.push("");
    parts.push(`${line.stage_display_name || line.work_text}: ${line.codes.length} ${noun}`);
    if (line.codes.length) parts.push(line.codes.join(", "));
  }
  parts.push("");
  parts.push(`Chưa nghiệm thu: ${pendingAcceptance} cấu kiện đã xong`);
  return parts.join("\n");
}

export function groupCodesByPrefix(codes: Array<{ code: string; unknown?: boolean }>) {
  const groups = new Map<string, Array<{ code: string; unknown?: boolean }>>();
  for (const item of codes) {
    const prefix = (item.code.match(/^[A-Za-z]+/)?.[0] ?? "#").toUpperCase();
    groups.set(prefix, [...(groups.get(prefix) ?? []), item]);
  }
  return [...groups.entries()];
}
