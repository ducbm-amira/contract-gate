# Gap-audit + Câu hỏi QA — Công cụ 売却活動報告書

**Loại task:** greenfield (design + spec mới, không legacy) → oracle = **design × spec soi chéo** + chuẩn ngành + journey.
**Nguồn:** `SPEC.md` + `design.html` (prototype tương tác v2, đã trace cả JS).
**Ngày:** 2026-07-05.

> Cách đọc: 🔴 = **blocker** (không rõ thì không build đúng được) · 🟡 = **confirm** (build được với default, cần khách xác nhận). Mỗi câu có **đề xuất của mình** + **default nếu khách im lặng**.

---

## PHẦN 0 — Design × Spec soi chéo (bức tranh nhanh)

| Loại | Nội dung |
|---|---|
| **SPEC có, design THIẾU** | ① Cấu trúc hóa địa chỉ (prefecture/location/town) ② Matching bảng `sale_` bằng địa chỉ+免許 (design dùng data giả) ③ Hành vi **nhân bản** phân biệt còn-hạn/hết-hạn (§6) ④ Sinh **PDF thật** |
| **Design ↔ Spec MÂU THUẪN** | ⑤ Mesh biểu đồ **màn nhập**: SPEC nói luôn 1 tuần; design report-5 lại mesh 2 tuần theo loại HĐ ⑥ **見学**: SPEC nhập theo tuần×kênh; design tách thành log tự do (report-6) |
| **Design THÊM, spec không nhắc** | ⑦ Màn 競合事例 (report-7, nặng: filter+chọn≤10+biểu đồ giá) ⑧ 顧客情報+敬称 (report-9) ⑨ レインズ chi tiết (report-3) ⑩ 物件確認 (report-2) ⑪ settings/連携媒体 |

---

## PHẦN 1 — CÂU HỎI CHO KHÁCH (gửi qua BrSe)

Chỉ những thứ **khách mới quyết được** (scope / business rule / mâu thuẫn). Việc dev tự làm/tự quyết ở Phần 2.

### 🔴 Q1 — Mesh biểu đồ ở màn NHẬP (mâu thuẫn design vs spec)
Spec §5: *"màn nhập luôn theo đơn vị 1 tuần, chỉ PDF mới mesh theo kỳ (1/2 tuần)"*. Nhưng design report-5 (媒体サマリー, hiện trong app) đang **mesh 2 tuần** theo loại HĐ.
- (A) Theo SPEC — màn nhập/summary luôn 1 tuần, chỉ PDF mesh.
- (B) Theo design — màn summary cũng mesh theo kỳ.
→ **Đề xuất: A** (spec rõ + hợp lý cho việc nhập/kiểm). **Default nếu im lặng: A.**

### 🔴 Q2 — Cấu trúc hóa địa chỉ có trong v1 không?
Spec §2 yêu cầu: nhập địa chỉ → hiện prefecture/location/town cỡ nhỏ dưới ô, lưu để matching `sale_`. Design **hoàn toàn không có**.
- (A) Cần cho v1 (vì là **khóa matching** BĐS môi giới).
- (B) Hoãn v2, v1 nhập tay/chọn tay.
→ **Đề xuất: A** nếu tính năng "tự lấy BĐS từ sale_" là core; nếu không thì B. **Kèm hỏi dev-side:** dùng API cấu trúc hóa địa chỉ nào? **Default: A.**

### 🔴 Q3 — Nhân bản (§6) có trong v1 không? (effort lớn)
Spec §6 định nghĩa nhân bản **khác nhau** khi HĐ còn hạn (kế thừa tuần đã nhập) vs hết 3 tháng (reset tuần 1). Design chỉ "load như tạo mới", **chưa có logic này**.
- (A) v1 phải có đủ 2 nhánh.
- (B) v1 làm nhân bản đơn giản (copy), logic 2 nhánh để v2.
→ **Đề xuất: hỏi priority** — đây là logic phức tạp, ảnh hưởng estimate. **Default: B** (không âm thầm làm thiếu — báo rõ).

### 🟡 Q4 — 見学 nhập kiểu nào? (mâu thuẫn)
Spec §4: 見学 nhập **theo tuần × kênh** cùng PV/phản hồi. Design: 見学 là **log tự do** (report-6: ngày/種別/memo), không gắn lưới tuần.
- (A) Theo design — log tự do (giàu hơn, gắn ngày cụ thể).
- (B) Theo spec — ô số trong lưới tuần×kênh.
→ **Đề xuất: A** (log ngày cụ thể hợp thực tế xem nhà hơn ô đếm). **Default: A** — nhưng nói rõ đã lệch spec.

### 🟡 Q5 — Các màn design tự thêm: giữ hết trong v1?
Design có mà spec không nhắc: **競合事例** (report-7 — nặng nhất), 顧客情報+敬称, レインズ chi tiết, 物件確認.
- Xác nhận: khách đã duyệt các màn này? Cái nào **v1**, cái nào bỏ/hoãn?
→ **Đề xuất:** giữ (design khách tự thêm = ý đồ thật, theo nguyên tắc "đừng bỏ thứ khách đã vẽ"), nhưng **競合事例 tốn effort lớn** → confirm priority riêng. **Default: giữ tất, flag effort 競合事例.**

### 🟡 Q6 — Model AI + hành vi khi lỗi + ràng buộc ký tự
Spec §7 prompt giàu placeholder (PV/累計/前期比/競合/値下げ率/thương lượng…) nhưng design chỉ truyền tên+diện tích; enforce 180–230 / 200–250 ký tự chưa rõ; AI lỗi/timeout chưa có UX.
- Model nào? · Ký tự: cắt/regenerate nếu lệch hay chỉ gợi ý? · Lỗi AI → cho nhập tay + thử lại?
→ **Đề xuất:** prompt **đầy đủ theo spec**; ký tự chỉ hướng dẫn (không cắt cứng); lỗi → nhập tay + retry. **Default: như đề xuất.**

### 🟡 Q7 — "BĐS đang đăng" trong `sale_` lọc theo gì? + khớp nhiều/không khớp
Spec §2 nói lấy "BĐS đang trong HĐ môi giới" theo địa chỉ+免許. Cần khách/BE làm rõ: điều kiện "đang đăng" = trạng thái nào? Khớp **nhiều** BĐS thì hiện sao? Khớp **0** → chỉ nhập tay?
→ **Đề xuất:** khớp nhiều = list chọn; 0 = fallback nhập tay (design đã có nút này). **Default: như đề xuất.** *(Data shape thật lấy từ BE — xem D6.)*

### 🟡 Q8 — 一般/代理 = kỳ 2 tuần (xác nhận nhanh)
Spec: 専属専任=1 tuần, còn lại (専任/一般/代理)=2 tuần. Design chỉ map tường minh 専属専任 & 専任; 一般/代理 rơi vào default 2 tuần.
→ **Đề xuất/Default: 2 tuần** (đúng spec) — chỉ cần khách gật.

---

## PHẦN 2 — VIỆC DEV TỰ VERIFY / QUYẾT (không cần hỏi khách)

Đây là phần **tự xử**, không đẩy lên khách — nhưng phải làm/flag, không âm thầm bỏ.

- **D1 🔴 — Test logic 13/14 tuần.** Design tính bằng `Date` native (`setMonth+3`, tự clamp cuối tháng + năm nhuận) → *có vẻ* đúng nhưng **CHƯA test đối chiếu bảng đầy đủ SPEC §3** (31/3→13 tuần, 29/11 chỉ 14 tuần khi năm nhuận…). **Đây là chỗ bug dễ trốn nhất** → viết characterization test phủ từng ca trong bảng trước khi tin.
- **D2 🔴 — "Hôm nay" đang bất nhất:** code lẫn `new Date()` (máy) và `SR_TODAY=2026/6/12` (cố định) → grayout tuần/số kỳ có thể lệch khi chạy thật. Chốt **1 nguồn thời gian** (đề xuất JST server-side) — liên quan Q… nhưng phần "neo theo gì" thì nên hỏi khách nếu mơ hồ; phần "hết bất nhất" là bug dev.
- **D3 — PDF thật + nhánh "no media → bỏ trang phản hồi trong PDF".** Design mới chỉ skip màn trong app (`goFromR4`), chưa có PDF nên nhánh bỏ-trang-trong-PDF chưa kiểm được.
- **D4 — Validation không nhất quán:** report-8 chặn nút khi thiếu (đúng spec §7), nhưng report-3 chỉ cảnh báo đỏ, **vẫn đi tiếp được** dù thiếu field. Thống nhất? (confirm với lead, không phải khách).
- **D5 — report-9 会社/顧客 field đang hardcode `defaultValue`,** không bind state → sửa không lưu. Phải wire thật vào company state.
- **D6 — API `sale_` thật:** design dùng data giả (`SR_PROPS`). Cần **contract response THẬT** từ BE (curl) trước khi build — pin data shape, đừng đoán *(bài học port-preflight-contract-first)*.

---

## PHẦN 3 — 7 lens đã soi (đảm bảo không sót)

| Lens | Kết quả |
|---|---|
| 1. State không vẽ | Empty/grayout/disabled: design **có**. Loading/error (AI có; fetch/PDF **thiếu**) → D3/D6 |
| 2. Data thật lệch | Địa chỉ fail, khớp nhiều/0, giá null → **Q7 + D6** |
| 3. Tương tác | Đã trace: modal công ty, calendar, skip report-5… (rõ). Validation lệch → **D4** |
| 4. Biên | 13/14 tuần + clamp + năm nhuận → **D1**; cap competitor 10 (có) |
| 5. Business rule | Cadence 一般/代理 → **Q8**; "hôm nay" neo gì → **Q6-time/D2**; nhân bản → **Q3** |
| 6. Nhất quán | Mesh màn nhập → **Q1**; 見学 → **Q4**; validation → **D4** |
| 7. Thiếu vs cố tình bỏ | Địa chỉ cấu trúc hóa (**Q2**), nhân bản (**Q3**), màn thêm (**Q5**) |
