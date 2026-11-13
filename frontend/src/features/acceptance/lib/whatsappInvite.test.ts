import { describe, expect, it } from "vitest";
import {
  buildAcceptanceScope,
  buildWhatsAppInvite,
  formatVietnameseDate,
  whatsAppInviteUrl,
} from "./whatsappInvite";

describe("WhatsApp acceptance invite", () => {
  it("counts beam codes and adds quantity + location", () => {
    expect(
      buildWhatsAppInvite({
        content: "công tác lăn keo, rắc cát tạo nhám dầm phát sinh",
        subject:
          "dầm I-19-21, F-16-18, F-18-19, F-19-21, F-31-33, F-19-25, I-18-21, I -16-18",
        location: "Phân đoạn 1 - Cầu chính",
        inspection_time: "18h00",
        request_date: "2026-11-13",
      }),
    ).toBe(
      "Kính mời CĐT, TVGS nghiệm thu công tác lăn keo, rắc cát tạo nhám dầm phát sinh tại 8 dầm Phân đoạn 1 - Cầu chính vào lúc 18h00 ngày 13/11/2026.Trân trọng!",
    );
  });

  it("uses the location count when subject is empty", () => {
    expect(
      buildWhatsAppInvite({
        content: "Sơn chống tia UV phạm vi dán sợi cọc",
        subject: "",
        location: "Cọc F1, F2, F3",
        inspection_time: "",
        request_date: "2026-11-13",
      }),
    ).toBe(
      "Kính mời CĐT, TVGS nghiệm thu Sơn chống tia UV phạm vi dán sợi cọc tại 3 cọc F1, F2, F3 ngày 13/11/2026.Trân trọng!",
    );
  });

  it("does not infer a quantity from commas in descriptive content", () => {
    expect(
      buildAcceptanceScope(
        "Đục bê tông om vỡ, tẩy gỉ cốt thép dầm phát sinh",
        "",
        "Phân đoạn 1 - Cầu chính",
      ),
    ).toBe("Phân đoạn 1 - Cầu chính");
  });

  it("falls back to comma-separated list when codes are not recognisable", () => {
    expect(
      buildAcceptanceScope("", "dầm A, B, C,", "Phân đoạn 1 - Cầu chính"),
    ).toBe("3 dầm Phân đoạn 1 - Cầu chính");
  });

  it("does not duplicate a quantity already present in content", () => {
    expect(
      buildWhatsAppInvite({
        content: "công tác đục 8 dầm phát sinh",
        subject: "dầm I-19-21, F-16-18, F-18-19, F-19-21, F-31-33, F-19-25, I-18-21, I -16-18",
        location: "Phân đoạn 1 - Cầu chính",
        inspection_time: "15h00",
        request_date: "2026-11-13",
      }),
    ).toBe(
      "Kính mời CĐT, TVGS nghiệm thu công tác đục 8 dầm phát sinh tại Phân đoạn 1 - Cầu chính vào lúc 15h00 ngày 13/11/2026.Trân trọng!",
    );
  });

  it("falls back to subject and omits missing time/date parts", () => {
    expect(
      buildWhatsAppInvite({
        content: "",
        subject: "Nghiệm thu cọc nhóm 2",
        location: "",
        inspection_time: "",
        request_date: null,
      }),
    ).toBe("Kính mời CĐT, TVGS nghiệm thu Nghiệm thu cọc nhóm 2.Trân trọng!");
  });

  it("formats dates and creates a share URL", () => {
    expect(formatVietnameseDate("2026-11-13")).toBe("13/11/2026");
    expect(formatVietnameseDate(null)).toBe("");
    expect(whatsAppInviteUrl("Kính mời CĐT")).toContain(
      "https://wa.me/?text=K%C3%ADnh%20m%E1%BB%9Di%20C%C4%90T",
    );
  });
});
