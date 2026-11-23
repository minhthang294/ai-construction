# UX audit — Tổng quan / Cấu kiện / Hiện trường / Nghiệm thu / Hỏi AI

**Ngày:** 2026-11-23 · **Chế độ:** read-only, không sửa code (chỉ tạo file báo cáo này)
**Persona:** kỹ sư hiện trường, găng tay, nắng chói, sóng yếu, thao tác một tay, ~5 phút cuối ngày; đã viết tiến độ trong Zalo, sau đó phải làm nhật ký và PYC/BBNT.
**Định hướng đã duyệt:** dán tin nhắn Zalo → xem mặt bằng → trả lời điểm mơ hồ bằng nút → lưu; một lần nhập sinh Zalo summary/nhật ký/danh sách chờ nghiệm thu; map-first; ảnh gắn cọc; nhập ngày < 2 phút.

## Phương pháp và bằng chứng

Đã xem ảnh chụp thật (điện thoại 390px, desktop 1440px) trong
`C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/shots`:
`phone-0..4-top/full`, `desktop-0..3-top/full`. Các màn không có trong bộ ảnh
(luồng dán tin nhắn sau khi bấm nút, batch manager, lịch sử sửa tiến độ) được
audit bằng code. Không có E2E tương tác trực tiếp, nên số tap là ước tính từ
luồng code/UI.

Điểm đang làm tốt: nút “Dán tin nhắn Zalo” đã có ở Tổng quan, Hiện trường và
khối tiến độ trong ngày; ngày mặc định/ngày sửa được; chip mã và cảnh báo đỏ;
map preview có highlight; nút ≥44px ở phần lớn form mới; empty state cho PYC,
ảnh, đợt thi công, hồ sơ AI; batch selector nhớ theo project; không tự ghi khi
chưa xác nhận.

## Top 10 vấn đề theo tác động với kỹ sư hiện trường

### 1. Ảnh hiện trường không gắn được vào cọc/cấu kiện — chỉ là ô chữ tự do

- **Màn hình:** Hiện trường → Ảnh hiện trường; bộ lọc ảnh.
- **Bằng chứng:** `phone-2-full.png` (ô “Hạng mục (vd: Bê tông)”); code
  `frontend/src/features/site/components/PhotoCapture.tsx:602-607` và
  `:773-776` dùng `<input>` free text cho `component`; chỉ có work-item select
  `:580-591`. Không có picker theo mã cọc/cấu kiện hay batch.
- **Tác động:** đúng hướng “ảnh gắn cọc” bị phá; ảnh không thể đối chiếu tự động
  với tiến độ/nghiệm thu; lọc theo “Hạng mục” phụ thuộc cách gõ của từng người
  (Bê tông / bê tông / F67 / cọc F67), dễ mất bằng chứng khi cần PYC/BBNT.
- **Fix:** thay ô chữ bằng picker tìm mã cọc/dầm trong batch/zone hiện tại,
  lưu `component_id` (giữ text làm caption phụ); chip mã trên thumbnail; filter
  theo cấu kiện thật.
- **Effort:** M.

### 2. Một lần dán mới chỉ ra Zalo summary + progress; chưa sinh nhật ký/PYC/daily report

- **Màn hình:** luồng dán tin nhắn → kết quả; liên kết sang Nghiệm thu.
- **Bằng chứng:** `ProgressPastePanel.tsx:282` chỉ gọi `saveDailyProgress`;
  `:336-345` dựng Zalo text; `:755-757` chỉ `onOpenAcceptance()` điều hướng,
  không truyền batch/cấu kiện/ngày. Trang Hiện trường vẫn là một form báo cáo
  ngày riêng (`SiteReportPage.tsx:676+`), nhật ký là tab riêng; Nghiệm thu tạo
  PYC tay (`AcceptancePage.tsx:884-895`).
- **Tác động:** kỹ sư vẫn phải làm thêm 2-3 luồng sau khi đã “xong” tiến độ;
  mất ngữ cảnh batch/khu khi sang Nghiệm thu; không đạt mục tiêu “một lần nhập”
  và khó giữ < 5 phút cuối ngày.
- **Fix:** sau commit hiện một “Bước tiếp theo” với 3 nút đã prefill:
  (a) tạo/cập nhật báo cáo ngày từ chính các sự kiện vừa ghi, (b) tạo nhật ký
  ngày (preview/snapshot), (c) tạo PYC nháp từ danh sách chưa nghiệm thu của
  batch; deep-link mang `batch_id`, `event_date`, `component_ids`.
- **Effort:** L.

### 3. Tổng quan: KPI quan trọng bị chôn dưới ~20 thanh đoạn; hai thẻ “Báo cáo ngày” và CTA trùng nhau

- **Màn hình:** Tổng quan.
- **Bằng chứng:** `phone-0-full.png` — 4 thẻ KPI nằm sau toàn bộ danh sách đoạn;
  `CorePages.tsx:565-582` render “Tiến độ theo đoạn” trước KPI; `:524` có
  “Báo cáo ngày gần nhất” và `:541` có thẻ “Báo cáo ngày” (trạng thái hôm nay),
  dễ nhầm là cùng một báo cáo. `:474-490` có 5 quick action + CTA
  “Cập nhật hiện trường”, trùng “Báo cáo hiện trường”/“Hiện trường”.
- **Tác động:** trên điện thoại, “Cần xử lý/Hoàn thành chưa nghiệm thu” nằm
  ngoài 4-5 màn cuộn; kỹ sư không thấy việc gấp. Hai thẻ ngày gây hiểu sai
  “hôm nay chưa có báo cáo” dù ngày gần nhất 22/11 đã có.
- **Fix:** đưa 4 KPI lên ngay dưới batch selector; gộp hai thẻ báo cáo thành một
  thẻ “Ngày gần nhất” có toggle hôm nay/ngày gần nhất; bỏ CTA trùng hoặc đổi
  thành hành động chính duy nhất; thanh đoạn chỉ hiện 3 đoạn có hoạt động +
  “Xem tất cả”.
- **Effort:** M.

### 4. Nghiệm thu bị chiếm chỗ bởi danh bạ + cấu hình số; không có danh sách chờ nghiệm thu để tạo PYC

- **Màn hình:** Nghiệm thu.
- **Bằng chứng:** `phone-3-full.png` — “Danh bạ người tham gia” và “Cấu hình số
  PYC/BBNT” chiếm phần lớn màn trước khi có PYC; code render vô điều kiện
  `AcceptancePage.tsx:991` và `:1287-1298`; CTA tạo chỉ có “+ Tạo PYC nháp”
  `:884-890`; danh sách PYC rỗng `:893-895`.
- **Tác động:** kỹ sư muốn lập PYC cho 14 cọc vừa xong phải qua form trống,
  không thấy cấu kiện chờ nghiệm thu, dễ tạo PYC sai/thiếu; cấu hình số là việc
  quản trị, không phải việc hiện trường.
- **Fix:** đưa “Chờ nghiệm thu (N cấu kiện)” lên đầu tab PYC, chọn batch/cấu kiện
  và “Tạo PYC từ lựa chọn”; chuyển Danh bạ/Cấu hình vào “Cài đặt” đóng mặc định
  và gate theo role admin/PM.
- **Effort:** M-L.

### 5. Câu hỏi dán tin nhắn tăng theo từng cấu kiện, không có “áp dụng cho cả dòng”, dễ thành hàng chục tap

- **Màn hình:** luồng dán tin nhắn (sau khi đọc tin).
- **Bằng chứng:** mỗi câu hỏi là một card, mọi câu phải trả lời
  `ProgressPastePanel.tsx:588-620`, `answeredAll` chỉ bật nút khi đủ
  `:150`; backend sinh câu hỏi stage theo từng component
  (`backend/app/engineering_ai/progress_parse.py:437-459`). Chọn công đoạn ở
  cấp dòng không thay thế được câu hỏi per-component.
- **Tác động:** golden 22/11 đã có ~6 câu; tin có nhiều dầm (3 công đoạn mỗi
  dầm) sẽ thành 20+ card, cuộn dài, dễ bỏ dở; mục tiêu <2 phút không giữ được.
- **Fix:** gom câu hỏi theo dòng/loại, thêm “Áp dụng công đoạn này cho cả dòng”,
  auto-answer khi chỉ có 1 ứng viên, hiển thị sticky “còn N câu” và cho phép
  nhảy tới câu chưa trả lời.
- **Effort:** M.

### 6. “Map-first” chưa xảy ra: mặt bằng là tab thứ 5, form tiến độ là mặc định, không có map trên Tổng quan

- **Màn hình:** Cấu kiện / Tổng quan.
- **Bằng chứng:** `ComponentCatalogImport.tsx:44-50` đặt “Mặt bằng” cuối 5 tab;
  mặc định `view="daily"` `:173`; `phone-1-top.png` cho thấy tab wrap 2 hàng và
  form “Tiến độ trong ngày” chiếm màn; không có lối tắt mặt bằng từ
  Tổng quan/latest-day.
- **Tác động:** kỹ sư không nhìn thấy cọc/khu trước khi ghi; khó chọn đúng cấu
  kiện bằng ngón tay; định hướng map-first bị đảo.
- **Fix:** mặc định mở map (hoặc split map + danh sách) trên Cấu kiện; tap marker
  mở bottom sheet tiến độ/ảnh/lịch sử; thêm “Mở mặt bằng” từ Tổng quan và kết quả
  dán tin.
- **Effort:** L.

### 7. Nhiều vùng chạm nhỏ hơn 44px ở các việc chính

- **Màn hình:** Hiện trường (ngày, ảnh), Nhật ký, Xuất báo cáo, Nghiệm thu.
- **Bằng chứng:** mũi tên ngày `SiteReportPage.tsx:689,705` `min-h-8` (32px),
  input ngày `:696` `min-h-9`; nút ảnh/lọc ảnh `PhotoCapture.tsx:272,278,284,
  298,306,314,322,687,811,818` `min-h-9`; Journal `JournalPanel.tsx:306,316,352`;
  Export `ExportPanel.tsx:150,158,191`; ô “Thêm vào danh bạ”
  `RequestForm.tsx:325` `min-h-9`.
- **Tác động:** găng tay + nắng + một tay dễ bấm trượt, đặc biệt mũi tên đổi
  ngày và nút ảnh; sai ngày ảnh hưởng toàn bộ báo cáo.
- **Fix:** tối thiểu `min-h-11 min-w-11` cho mọi control tương tác; kiểm tra
  tự động bằng test/rule Tailwind.
- **Effort:** S.

### 8. Chữ phụ 10-12px, xám nhạt; khó đọc ngoài trời

- **Màn hình:** tất cả.
- **Bằng chứng:** `App.tsx:327` label dự án 10px `text-slate-400`; mô tả/ghi chú
  12px `text-slate-500`/`gray-500` rất nhiều (`SiteReportPage.tsx:800`,
  `PhotoCapture.tsx:560`, `CorePages.tsx:544-554`); nav mobile 11px
  (`App.tsx:559+`). `slate-400` trên trắng chỉ ~2.6:1, dưới WCAG AA.
- **Tác động:** ngoài nắng, người lớn tuổi hoặc mắt mỏi không đọc được helper
  text/trạng thái; dễ hiểu sai trạng thái “Nháp/Đã duyệt”, “Chưa có”.
- **Fix:** chữ nghiệp vụ tối thiểu 14px, label 12-13px đậm; dùng
  slate-600/700; tăng status chip; thêm chế độ tương phản cao/outdoor (nền
  trắng, chữ đen, viền đậm).
- **Effort:** S-M.

### 9. Điều hướng và từ ngữ chưa thống nhất, có nút “Quay lại” thừa ở trang cấp 1

- **Màn hình:** app shell, Cấu kiện, Tổng quan.
- **Bằng chứng:** `App.tsx:490-492` render “Quay lại” cho mọi trang trừ Tổng
  quan/Công trình, dù đã có bottom nav; `phone-1..4-top.png` đều có nút này.
  Batch option ghi “Tất cả công trình” nhưng nghĩa là “không lọc đợt”
  (`ConstructionBatchSelector.tsx:29`). “PD2” (overview) và “PĐ 2” (danh sách)
  xen kẽ; “Hỏi AI” (nav) vs “Hỏi đáp AI hồ sơ kỹ thuật”/“Chat có citation”
  (Hỏi AI); “Tổng đã biết” (nhân lực) mơ hồ.
- **Tác động:** thêm một tap và một dòng nhiễu trước nội dung; từ ngữ “công
  trình/đợt”, “PD/PĐ”, “hồ sơ/AI” làm người dùng phải suy luận.
- **Fix:** bỏ “Quay lại” ở 5 trang cấp 1 (chỉ giữ trong chi tiết); đổi option
  thành “Tất cả đợt”; thống nhất “PĐ”; chuẩn hóa “Hỏi AI”, bỏ “citation/chat”
  khỏi tiêu đề hiển thị; đổi “Tổng đã biết” → “Tổng nhân lực đã nhập”.
- **Effort:** S.

### 10. Ngôn ngữ màu trạng thái không nhất quán giữa thi công và nghiệm thu

- **Màn hình:** Tổng quan, Cấu kiện, Hiện trường, Nghiệm thu.
- **Bằng chứng:** biểu đồ tổng dùng xanh lá cho “Hoàn thành”
  (`ConstructionProgressChart.tsx:14`), nhưng thanh theo đoạn dùng xanh dương
  cho thi công và xanh lá cho nghiệm thu (`SegmentProgressBars.tsx:53,71`).
  Nút lưu Hiện trường dùng `bg-green-700` (`SiteReportPage.tsx:933`); Nghiệm thu
  dùng teal-700 (`AcceptancePage.tsx:780,887,921`), nút xác nhận emerald
  (`:1201`); CTA app dùng #405e9b. Cùng xanh lá mang nghĩa “hoàn thành thi
  công”, “đã nghiệm thu”, “lưu thành công”.
- **Tác động:** ngoài trời/ít thời gian, người dùng dựa vào màu để đọc trạng
  thái; cùng màu cho hai cột độc lập dễ nhầm tiến độ với nghiệm thu.
- **Fix:** design token 2 hệ: thi công = xanh dương (đậm/nhạt theo trạng thái),
  nghiệm thu = xanh lá + icon/hình dạng riêng; primary action = brand #405e9b
  (không dùng xanh lá cho Save); ghi rõ trong style guide.
- **Effort:** M.

## Quick wins (làm trong 1-2 ngày)

1. **Reset lỗi Tổng quan:** `setSummaryFailed/latestFailed/segmentsFailed` chỉ
   set true, không bao giờ false (`CorePages.tsx:431,445,447`); thêm reset và
   nút “Thử lại” khi đổi batch/project.
2. **Bỏ “Quay lại” ở trang cấp 1** (`App.tsx:490`), giữ cho chi tiết.
3. **Tăng touch target** các `min-h-8/9` đã liệt kê lên `min-h-11 min-w-11`.
4. **Đổi “Tất cả công trình” → “Tất cả đợt”** trong batch selector.
5. **Gộp/đổi tên hai thẻ báo cáo** ở Tổng quan; bỏ CTA trùng.
6. **Giới hạn thanh đoạn** ở Tổng quan: 3 đoạn có hoạt động + “Xem tất cả”.
7. **Hỏi AI:** thu gọn hero, ẩn “Đổi tên/Xóa” khi chưa có hội thoại
   (`ChatPanel.tsx:326-341`), đưa ô hỏi lên trước “Hồ sơ nguồn”.
8. **Batch empty:** thêm nút “Tạo đợt” ngay trong selector khi danh sách rỗng;
   hiện tại phải tự sang Cấu kiện → Quản lý đợt.
9. **Tăng chữ helper quan trọng** từ 10-12px lên 14px và `slate-600`.
10. **Thêm label/aria cho select ảnh** (`PhotoCapture.tsx:568-591`) và các
    filter chỉ có placeholder (`:757+`).
11. **Hỏi AI:** bỏ pill “Chat có citation” và copy lặp giữa hero và ChatPanel.
12. **Nghiệm thu:** ẩn/collapse “Cấu hình số” và “Danh bạ” sau disclosure, gate
    role; đưa nút tạo PYC lên đầu.

## Đề xuất thiết kế lại lớn hơn

1. **“Một lần nhập” thực sự:** sau khi duyệt tiến độ, tạo một “Field entry” gồm
   progress events + daily report draft + journal snapshot + PYC draft trong
   cùng một màn xác nhận. Các bước sau chỉ là “Bổ sung ảnh/nhân lực” và “Xuất”.
   Điều này mới đạt mục tiêu 5 phút cuối ngày.
2. **Map-first workspace:** Cấu kiện mở thẳng mặt bằng với batch hiện tại; marker
   mở bottom sheet gồm trạng thái, ảnh, lịch sử, nút “Ghi tiến độ/Dán tin”. Danh
   sách chỉ là chế độ phụ. Từ Tổng quan/latest-day deep-link vào đúng marker.
3. **Nghiệm thu theo hàng đợi:** tab PYC mặc định là “Chờ nghiệm thu” (batch,
   cấu kiện xong, ảnh, ngày), chọn nhiều → tạo PYC một lần; danh bạ/cấu hình
   chuyển vào Settings. Đây là nửa còn lại của “một lần nhập”.
4. **Design system hiện trường:** token màu/typography/touch target; hai hệ màu
   riêng cho thi công/nghiệm thu; chế độ “ngoài trời” (chữ 16px, tương phản
   cao); component picker dùng chung cho ảnh/tiến độ/PYC.
5. **Tổng quan = 3 việc hôm nay**, không phải dashboard phân tích: “Ghi tiến độ
   hôm nay”, “N cấu kiện chờ nghiệm thu”, “Ảnh/thiếu chứng cứ”; phần thống kê
   và thanh đoạn đưa vào tab “Phân tích” hoặc thu gọn.

## Ước tính số tap cho việc cuối ngày

| Việc | Đường hiện tại | Tap tối thiểu |
| --- | --- | --- |
| Ghi tiến độ bằng dán tin | Tổng quan → quick action → Dán/Đọc → trả lời N câu → Xem lại → tick → Ghi | **6 + N** (golden ~12; nhiều dầm có thể 20+) |
| Ghi tiến độ tay | Cấu kiện → chọn bước → mở danh sách → tick từng cọc → trạng thái → xem lại → tick → ghi | **~20+** với 14 cọc |
| Báo cáo ngày | Hiện trường → ghi chú/nhân lực/công việc → lưu | **10-20 input/tap**, chưa kể ảnh |
| Nhật ký | Cấu kiện → Nhật ký → preview → snapshot → xuất | **5+** và tách khỏi luồng dán |
| PYC | Nghiệm thu → tạo PYC → nhập form → lưu/xuất | **10+**, không prefill từ cọc vừa xong |

## Ghi chú thêm

- Ảnh full-page cho thấy bottom nav cố định cắt ngang nội dung ở một số màn
  (Hiện trường, Nghiệm thu, Hỏi AI); cần kiểm tra `padding-bottom` của main so
  với chiều cao nav + sticky action bar, đặc biệt thanh “Thêm công tác/Xem lại”
  trong Tiến độ trong ngày (`DailyProgressPanel.tsx` sticky bottom, z-20 dưới
  nav z-30).
- Danh sách ảnh render toàn bộ (`PhotoCapture.tsx:848`); với công trình nhiều
  ảnh cần phân trang/virtualize. Danh sách đoạn Tổng quan cũng render toàn bộ
  (`SegmentProgressBars.tsx:8-26`).
- Tab Cấu kiện 5 tab wrap 2 hàng trên 390px (`phone-1-top.png`), làm giảm diện
  tích above-the-fold; nên chuyển thành segmented scroll ngang hoặc 2 tầng rõ
  ràng (Tiến độ / Danh mục / Mặt bằng, còn Nhật ký vào menu).
- Chưa có E2E/kiểm thử tương tác thật trên thiết bị; các kết luận tap/scroll dựa
  trên ảnh và code, cần xác nhận với 2-3 kỹ sư hiện trường.
