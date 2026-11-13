export type QuestionCategoryId =
  | "location"
  | "dimensions"
  | "method"
  | "pages"
  | "sources"
  | "documents";

export type QuestionSuggestionMode = "send" | "fill";

export type QuestionSuggestion = {
  id: string;
  category: QuestionCategoryId;
  label: string;
  prompt: string;
  mode: QuestionSuggestionMode;
  badge?: "verified" | "proposed" | "navigation" | "caution";
};

export type QuestionCategory = {
  id: QuestionCategoryId;
  label: string;
  description: string;
};

export const QUESTION_CATEGORIES: QuestionCategory[] = [
  {
    id: "location",
    label: "Vị trí & phân đoạn",
    description: "Tra nhóm, phân đoạn, cầu và danh sách cọc/dầm.",
  },
  {
    id: "dimensions",
    label: "Kích thước & khối lượng",
    description: "Chiều sâu đục, vết nứt, diện tích, khối lượng.",
  },
  {
    id: "method",
    label: "Quy trình & biện pháp",
    description: "Trình tự xử lý và trang chỉ dẫn thi công.",
  },
  {
    id: "pages",
    label: "Mở trang & bản vẽ",
    description: "Mở nhanh trang thiết kế, bản vẽ hoặc thuyết minh.",
  },
  {
    id: "sources",
    label: "Nguồn & xác minh",
    description: "Kiểm tra trang nguồn và trạng thái dữ kiện.",
  },
  {
    id: "documents",
    label: "Thuyết minh & vật liệu",
    description: "Vật liệu, tiêu chuẩn, điều kiện thi công.",
  },
];

const ALL_QUESTIONS: QuestionSuggestion[] = [
  // Vị trí, nhóm, phân đoạn
  {
    id: "location-f27",
    category: "location",
    label: "F27 thuộc nhóm mấy, phân đoạn nào?",
    prompt: "Cọc F27 thuộc nhóm mấy, phân đoạn nào, cầu nào?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "location-q295",
    category: "location",
    label: "Dầm Q-295 ở đâu?",
    prompt: "Dầm Q-295 thuộc nhóm mấy, ở đâu?",
    mode: "fill",
    badge: "proposed",
  },
  {
    id: "location-h77",
    category: "location",
    label: "H77 thuộc nhóm mấy?",
    prompt: "Cọc H77 thuộc nhóm mấy?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "location-main-segment1-damaged",
    category: "location",
    label: "Cầu chính PĐ1 cọc nào hỏng?",
    prompt: "Cầu chính phân đoạn 1 có những cọc nào hư hỏng?",
    mode: "send",
    badge: "verified",
  },
  {
    id: "location-group2-main",
    category: "location",
    label: "Cọc nhóm 2 cầu chính cần sửa",
    prompt: "Cầu chính, cọc nhóm 2 cần sửa gồm những cọc nào?",
    mode: "send",
    badge: "caution",
  },
  {
    id: "location-group2-approach",
    category: "location",
    label: "Cọc nhóm 2 cầu dẫn cần sửa",
    prompt: "Cọc nhóm 2 cần sửa ở cầu dẫn gồm những cọc nào?",
    mode: "send",
    badge: "proposed",
  },
  {
    id: "location-group3-damaged",
    category: "location",
    label: "Cọc nhóm 3 bị nứt",
    prompt: "Cọc nhóm 3 bị nứt gồm những cọc nào?",
    mode: "send",
    badge: "proposed",
  },
  {
    id: "location-count-group2",
    category: "location",
    label: "Đếm cọc nhóm 2",
    prompt: "Có bao nhiêu cọc nhóm 2?",
    mode: "send",
    badge: "caution",
  },

  // Kích thước, khối lượng
  {
    id: "dimension-h77-depth",
    category: "dimensions",
    label: "H77 đục sâu bao nhiêu?",
    prompt: "Cọc H77 đục sâu bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-f27-crack",
    category: "dimensions",
    label: "F27 chiều dài vết nứt",
    prompt: "Cọc F27 chiều dài vết nứt bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-f27-depth",
    category: "dimensions",
    label: "F27 chiều sâu đục",
    prompt: "Cọc F27 chiều sâu đục bao nhiêu?",
    mode: "fill",
    badge: "proposed",
  },
  {
    id: "dimension-h77-glue",
    category: "dimensions",
    label: "H77 diện tích quét keo",
    prompt: "Cọc H77 diện tích quét keo epoxy bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-h77-volume",
    category: "dimensions",
    label: "H77 khối lượng đục",
    prompt: "Cọc H77 khối lượng đục bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-f27-l1",
    category: "dimensions",
    label: "F27 chiều dài L1",
    prompt: "Cọc F27 L1 bằng bao nhiêu?",
    mode: "fill",
    badge: "proposed",
  },
  {
    id: "dimension-beam-depth",
    category: "dimensions",
    label: "I-30-31 đục sườn/đáy",
    prompt: "Dầm I-30-31 đục sườn sâu bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-beam-fiber",
    category: "dimensions",
    label: "I-30-31 diện tích dán sợi",
    prompt: "Dầm I-30-31 diện tích dán sợi bao nhiêu?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "dimension-beam-patch",
    category: "dimensions",
    label: "G-F.89 khối lượng trám vá",
    prompt: "Dầm G-F.89 khối lượng trám vá bao nhiêu?",
    mode: "fill",
    badge: "proposed",
  },

  // Quy trình, biện pháp
  {
    id: "method-h77",
    category: "method",
    label: "Quy trình xử lý H77",
    prompt: "Quy trình xử lý cọc H77 là gì?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "method-beam",
    category: "method",
    label: "Quy trình xử lý I-30-31",
    prompt: "Quy trình xử lý dầm I-30-31 là gì?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "method-page-group2",
    category: "method",
    label: "Mở trang biện pháp thi công nhóm 2",
    prompt: "Mở trang biện pháp thi công cho cọc nhóm 2",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "method-page-group2-process",
    category: "method",
    label: "Mở trang quy trình cọc nhóm 2",
    prompt: "Mở trang quy trình xử lý cọc nhóm 2",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "method-page-fiber",
    category: "method",
    label: "Mở trang chỉ dẫn dán sợi",
    prompt: "Mở trang chỉ dẫn thi công dán sợi carbon",
    mode: "send",
    badge: "navigation",
  },

  // Mở trang, bản vẽ
  {
    id: "page-main-segment2",
    category: "pages",
    label: "Trang thiết kế cầu chính PĐ2",
    prompt: "Mở trang thiết kế cầu chính phân đoạn 2",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "page-main-segment2-group2",
    category: "pages",
    label: "Trang thiết kế cầu chính PĐ2 nhóm 2",
    prompt: "Mở trang thiết kế cầu chính phân đoạn 2 nhóm 2",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "page-pile-group2",
    category: "pages",
    label: "Mở bản vẽ nhóm cọc 2",
    prompt: "Mở bản vẽ nhóm cọc 2",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "page-beam-q295",
    category: "pages",
    label: "Mở bản vẽ dầm Q-295",
    prompt: "Mở bản vẽ dầm Q-295",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "page-8",
    category: "pages",
    label: "Mở trang 8",
    prompt: "Mở trang 8",
    mode: "send",
    badge: "navigation",
  },
  {
    id: "page-32",
    category: "pages",
    label: "Mở trang 32",
    prompt: "Mở trang 32",
    mode: "send",
    badge: "navigation",
  },

  // Nguồn, xác minh
  {
    id: "source-h77-depth",
    category: "sources",
    label: "Trang nào ghi chiều sâu H77?",
    prompt: "Trang nào ghi chiều sâu đục của cọc H77?",
    mode: "fill",
    badge: "verified",
  },
  {
    id: "source-h77-data",
    category: "sources",
    label: "H77 có những số liệu nào?",
    prompt: "Cọc H77 có những số liệu nào?",
    mode: "fill",
    badge: "verified",
  },

  // Thuyết minh, vật liệu, thi công
  {
    id: "document-patch-material",
    category: "documents",
    label: "Vật liệu trám vá bê tông",
    prompt: "Vật liệu trám vá bê tông theo hồ sơ là gì?",
    mode: "send",
  },
  {
    id: "document-epoxy",
    category: "documents",
    label: "Keo epoxy HM-180C3P",
    prompt: "Keo epoxy HM-180C3P dùng cho hạng mục nào?",
    mode: "send",
  },
  {
    id: "document-water-level",
    category: "documents",
    label: "Mực nước thi công yêu cầu",
    prompt: "Điều kiện mực nước thi công yêu cầu là bao nhiêu?",
    mode: "send",
  },
  {
    id: "document-schedule",
    category: "documents",
    label: "Thời gian thi công dự kiến",
    prompt: "Thời gian thi công dự kiến của công trình là bao nhiêu?",
    mode: "send",
  },
  {
    id: "document-daily-check",
    category: "documents",
    label: "Kiểm tra hàng ngày khi dán sợi",
    prompt: "Quy trình kiểm tra hàng ngày khi dán sợi là gì?",
    mode: "send",
  },
  {
    id: "document-frp-standard",
    category: "documents",
    label: "Nghiệm thu dán sợi FRP",
    prompt: "Tiêu chuẩn nghiệm thu dán sợi FRP theo hồ sơ là gì?",
    mode: "send",
  },
];

export const QUESTION_SUGGESTIONS = ALL_QUESTIONS;

export function suggestionsForCategory(
  category: QuestionCategoryId,
): QuestionSuggestion[] {
  return QUESTION_SUGGESTIONS.filter((item) => item.category === category);
}

export function suggestionBadgeLabel(
  badge: QuestionSuggestion["badge"],
): string | null {
  switch (badge) {
    case "verified":
      return "Đã xác minh";
    case "proposed":
      return "Đề xuất";
    case "navigation":
      return "Mở trang";
    case "caution":
      return "Cần đối chiếu";
    default:
      return null;
  }
}
