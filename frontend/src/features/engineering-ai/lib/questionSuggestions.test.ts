import { describe, expect, it } from "vitest";
import {
  QUESTION_CATEGORIES,
  QUESTION_SUGGESTIONS,
  suggestionBadgeLabel,
  suggestionsForCategory,
} from "./questionSuggestions";

describe("question suggestion catalog", () => {
  it("has a non-empty, uniquely identified question in every category", () => {
    const ids = QUESTION_SUGGESTIONS.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const category of QUESTION_CATEGORIES) {
      const items = suggestionsForCategory(category.id);
      expect(items.length).toBeGreaterThan(0);
      expect(items.every((item) => item.category === category.id)).toBe(true);
    }
  });

  it("keeps labels and prompts usable by the chat UI", () => {
    for (const item of QUESTION_SUGGESTIONS) {
      expect(item.label.trim().length).toBeGreaterThan(0);
      expect(item.prompt.trim().length).toBeGreaterThan(0);
      expect(["send", "fill"]).toContain(item.mode);
    }
  });

  it("fills code-specific questions and sends fixed navigation questions", () => {
    const f27 = QUESTION_SUGGESTIONS.find((item) => item.id === "location-f27");
    const page = QUESTION_SUGGESTIONS.find((item) => item.id === "method-page-group2");
    const pageEight = QUESTION_SUGGESTIONS.find((item) => item.id === "page-8");

    expect(f27?.mode).toBe("fill");
    expect(page?.mode).toBe("send");
    expect(pageEight?.mode).toBe("send");
    expect(page?.prompt.toLowerCase()).toContain("mở trang");
  });

  it("does not suggest known misrouted material questions", () => {
    const prompts = QUESTION_SUGGESTIONS.map((item) => item.prompt.toLowerCase());
    expect(prompts).not.toContain(
      "keo epoxy dùng cho cọc nhóm 2 là loại nào?",
    );
    expect(prompts).not.toContain(
      "chiều dày tấm sợi carbon dùng cho dầm nhóm 1 là bao nhiêu?",
    );
  });

  it("maps badge labels for the visible suggestion chips", () => {
    expect(suggestionBadgeLabel("verified")).toBe("Đã xác minh");
    expect(suggestionBadgeLabel("proposed")).toBe("Đề xuất");
    expect(suggestionBadgeLabel("navigation")).toBe("Mở trang");
    expect(suggestionBadgeLabel("caution")).toBe("Cần đối chiếu");
    expect(suggestionBadgeLabel(undefined)).toBeNull();
  });
});
