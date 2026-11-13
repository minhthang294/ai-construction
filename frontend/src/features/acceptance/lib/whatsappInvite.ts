import type { AcceptanceRequest } from "../types";

function text(value?: string | null): string {
  return (value ?? "").trim();
}

export function formatVietnameseDate(value?: string | null): string {
  const raw = text(value);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : raw;
}

const UNIT_RE = /\b(dầm|cọc)\b/i;
const EXPLICIT_QUANTITY_RE = /\b(\d{1,4})\s*(dầm|cọc)\b/i;
const CODE_RE =
  /(?<![A-Za-z0-9])[A-Z]{1,4}\s*(?:-\s*)?\d{1,3}(?:\s*-\s*\d{1,3})?(?![A-Za-z0-9])/g;

function explicitQuantity(
  value: string,
): { count: number; unit: "dầm" | "cọc" } | null {
  const match = EXPLICIT_QUANTITY_RE.exec(value);
  if (!match) return null;
  return {
    count: Number(match[1]),
    unit: match[2].toLowerCase() === "cọc" ? "cọc" : "dầm",
  };
}

function unitIn(value: string): "dầm" | "cọc" | null {
  const match = UNIT_RE.exec(value);
  if (!match) return null;
  return match[1].toLowerCase() === "cọc" ? "cọc" : "dầm";
}

function countCodes(value: string): number {
  return value.match(CODE_RE)?.length ?? 0;
}

function countCommaItems(value: string): number {
  if (!value.includes(",")) return 0;
  return value
    .split(/[,;]+/)
    .map((item) => item.trim())
    .filter(Boolean).length;
}

/** Derive "8 dầm Phân đoạn 1 - Cầu chính" from subject/location. */
export function buildAcceptanceScope(
  content: string,
  subject: string,
  location: string,
): string {
  const unit = unitIn(subject) || unitIn(location) || unitIn(content);
  const subjectExplicit = explicitQuantity(subject);
  const locationExplicit = explicitQuantity(location);

  let quantity: number | null = null;
  let quantityUnit = unit;
  if (subjectExplicit) {
    quantity = subjectExplicit.count;
    quantityUnit = subjectExplicit.unit;
  } else if (locationExplicit) {
    quantity = locationExplicit.count;
    quantityUnit = locationExplicit.unit;
  } else {
    const subjectCodes = countCodes(subject);
    if (subjectCodes > 0 && quantityUnit) {
      quantity = subjectCodes;
    } else {
      const locationCodes = countCodes(location);
      if (locationCodes > 0 && quantityUnit) {
        quantity = locationCodes;
      } else {
        // Fallback for lists whose item format is not a recognisable code.
        const subjectItems = countCommaItems(subject);
        if (subjectItems > 1 && quantityUnit) {
          quantity = subjectItems;
        } else {
          const locationItems = countCommaItems(location);
          if (locationItems > 1 && quantityUnit) {
            quantity = locationItems;
          }
        }
      }
    }
  }

  const contentHasQuantity = Boolean(explicitQuantity(content));
  const coreLocation = location
    .replace(/^\s*(?:\d{1,4}\s*)?(?:dầm|cọc)\s*[:\-]?\s*/i, "")
    .trim();
  if (quantity !== null && quantityUnit && !contentHasQuantity) {
    return [String(quantity), quantityUnit, coreLocation]
      .filter(Boolean)
      .join(" ");
  }
  return coreLocation;
}

/** Build the short WhatsApp invitation used after saving/exporting a PYC. */
export function buildWhatsAppInvite(
  request: Pick<
    AcceptanceRequest,
    "content" | "subject" | "location" | "inspection_time" | "request_date"
  >,
): string {
  const content =
    text(request.content) ||
    text(request.subject) ||
    "công tác nghiệm thu";
  const normalizedContent = content.replace(/[.;,\s]+$/, "");
  const location = text(request.location);
  const subject = text(request.subject);
  const scope = buildAcceptanceScope(content, subject, location);
  const place = scope ? ` tại ${scope}` : "";
  const time = text(request.inspection_time);
  const date = formatVietnameseDate(request.request_date);
  const when = [time ? `vào lúc ${time}` : "", date ? `ngày ${date}` : ""]
    .filter(Boolean)
    .join(" ");
  return `Kính mời CĐT, TVGS nghiệm thu ${normalizedContent}${place}${
    when ? ` ${when}` : ""
  }.Trân trọng!`;
}

export function whatsAppInviteUrl(invite: string): string {
  return `https://wa.me/?text=${encodeURIComponent(invite)}`;
}
