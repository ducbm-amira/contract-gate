# TOOL-REQUIREMENTS — `contract-gate`

> **Trạng thái:** ĐANG TÍCH DẦN (chưa đủ để build). Đây là requirement **chắt từ trải nghiệm thật** (chạy tay quy trình trên task 売却活動報告書), KHÔNG phải tưởng tượng — đúng tinh thần "hiểu trước khi build" áp lên chính việc build tool.
>
> **Mục đích tool:** 1 CLI standalone, project-agnostic, bake kỷ luật **understand → contract → verify** để chống bug do vibe-code. Không bake được "sự hiểu" (phần người) — chỉ ép QUY TRÌNH + GUARDRAIL. Đẩy GitHub, build bằng GSD.

---

## Kết luận đã rút (từ task-test #1: 売却活動報告書)

### R1 — Tool phải nhận biết LOẠI TASK, bật đúng bộ oracle/lens
- **port** (có legacy) → oracle = diff vs legacy manifest; gap tự lòi khi so.
- **greenfield** (design + spec mới, không legacy) → oracle = **design × spec soi chéo** + chuẩn ngành + journey; gap chỉ lòi khi tự dựng mô hình.
- *Bằng chứng:* task-test là greenfield; cách hunt gap khác hẳn port. (khớp ý `oracle-by-task-type`)

### R2 — Output lõi = bản gap-audit / contract (mẫu = `GAP-QA.md`)
Cấu trúc bắt buộc:
1. **Design × Spec soi chéo** — 3 rổ: SPEC-có-design-thiếu / design-có-spec-không-nhắc / mâu-thuẫn.
2. **7 lens** quét không sót: state / data thật / tương tác / biên / business-rule / nhất quán / thiếu-vs-cố-tình-bỏ.
3. **Tách 2 loại rõ ràng:** ❓câu hỏi cho KHÁCH (scope/business-rule — chỉ khách quyết) vs 🔧việc DEV tự xử (implement/verify/decide).
4. Mỗi mục: **option + đề xuất + 🔴blocker/🟡confirm + default nếu im lặng** (để BrSe chốt với khách JP trong 1 vòng, không mất round-trip).
- *Bằng chứng:* `GAP-QA.md` — chạy thật ra được, dùng gửi lead/BrSe luôn.

### R3 — Mỗi chỗ mù được gắn "LOẠI THƯỚC" verify, gate theo đúng loại
Tool không nói chung chung "hãy verify". Phân loại theo **có oracle rõ hay không**:

| Loại chỗ mù | Oracle? | Thước tool ép |
|---|---|---|
| Logic tất định (tuần/kỳ/grayout/nhân bản) | ✅ | **TDD — test rút từ spec** |
| Mềm (văn AI / layout PDF / UX) | ❌ | human review / eval / visual-fidelity check |

- Hệ quả tinh: **spec có bảng "giá trị định sẵn" (vd bảng 13/14 tuần) → biến thẳng thành test case** ("rút test từ spec" tự động một phần).
- *Bằng chứng:* vụ 13/14 tuần — spec tặng sẵn oracle → TDD là đúng thuốc; nhưng văn AI thì TDD vô dụng. (khớp hướng `pinrich-cycle-open-problems` "thiếu TDD")

### R4 — Với task UI: output "Screen × Element data-binding map" + gate nguồn data
Có nhiều TẦNG spec: business (luật) / UI (màn hiện gì) / **data-binding (ô này lấy data từ đâu)** / test. Tầng data-binding **thường thiếu** và là nơi bug UI/migration trốn.
- Tool phải đẻ map: mỗi màn → mỗi phần tử → {loại: title/label/image/**data**/action/state} → với data: **nguồn (API/field/computed) + format + xử lý null/empty**.
- **Gate:** ô loại "data" mà chưa ghi nguồn = chưa cho build.
- *Bằng chứng:* cột "Data lấy từ đâu" + "State" là 2 cột đẻ bug nhất (LAND null, field 0-usage). Buộc curl API thật, pin shape — khớp `port-preflight-contract-first`.

### R5 — Verify data-binding bằng "golden record" (không tin spec suông)
Spec ghi "giá ← sale_.price" là HYPOTHESIS, chưa chắc đúng. Cách BIẾT hiển thị đúng data từ DB:
- Chọn 1 record **đã biết đáp án** (biết trước giá/tên thật trong DB) → mở màn → so khớp không.
- Kiểm ca khó: 0 / null / số rất dài / format 万円.
- → oracle = **giá trị thật của 1 record biết trước**. Spec pin NGUỒN; golden-record xác nhận WIRING nguồn→màn thật sự đúng.

---

## Nguyên lý thiết kế tool (ràng buộc — chống chính cái bẫy của SDD)

- **DP1 — Chỉ spec CHỖ MÙ, không spec mọi thứ.** 80% màn là hiển nhiên (AI làm đúng) → khỏi spec. Chỉ spec 20% rủi ro (data-binding, edge, business rule). Over-spec mọi thứ = tốn công ngang code + rơi vào "form cứng gò bó". Tool phải **hướng người dùng vào chỗ mù**, không bắt điền form dài.
- **DP2 — Ưu tiên dạng THỰC THI (test) hơn văn xuôi.** Spec chi tiết ≈ testcase — nhưng test **tự kiểm**, còn văn xuôi thì người phải kiểm tay. Với phần logic, tool nên đẩy contract thành TEST, không phải prose.
- **DP3 — Doc-time phải NHỎ + NET-saving.** 20 phút spec chỗ-mù < 3h debug (bài port-preflight: 3 commit rework). Nhưng chỉ đúng nếu spec đúng-chỗ + để **AI draft** map/test (người review), không gõ tay. Nếu tool làm doc-time phình = tool thất bại.
- **DP4 — Spec là hypothesis, phải verify vs reality.** "Code đúng theo spec" ≠ "đúng thật" — spec có thể sai. Luôn cặp spec với 1 oracle thật (golden record / test / browser).

---

## Còn phải đào thêm (chưa đủ requirement)

- [ ] Chạy thêm 1–2 task khác (đặc biệt 1 task **port có legacy**) để chắc mẫu output R2 đúng cho cả 2 nhánh, không chỉ greenfield.
- [ ] Format file contract thực tế: YAML hay markdown? mục nào bắt buộc/cấu hình được per-repo?
- [ ] Cơ chế "gate": kiểm gì để ra PASS/FAIL/BLOCKED? (mục bắt buộc đã điền? blocker đã resolve? test logic đã có + xanh?)
- [ ] Tool tự sinh chỗ mù (gợi ý) hay chỉ kiểm file người điền? (mức "thông minh")
- [ ] Cắm vào đâu: git pre-commit / CI / gọi tay — interface exit code 0/1/2.

---

## QUYẾT: đóng gói = **B (bolt vào GSD/pinrich-cycle)**, KHÔNG repo standalone
Lý do: rẻ nhất, giảm bug cho chính mình ngay, và ~70% đã có sẵn trong pinrich-cycle/port-harness.

## ĐÃ CÓ SẴN (dùng nguyên, ĐỪNG build lại)
- Verdict discipline `pass/fail` + exit 0/1/2; parser pipe-table stdlib (dùng chung 6 script).
- `manifest_gate` / `greenfield_gate` — oracle-present gate 2 nhánh (port vs greenfield).
- `characterize.py` (coverage legacy→React); `characterize_pdf/manifest` (assert Observable "present AND correct" — **chính là lõi R5**).
- `coverage_gate` / `evidence_gate` — nhánh mềm R3 (human-review/eval, đủ 5 chiều gồm text).
- Đã wire sẵn vào `/pinrich-cycle`.

## BUILD PLAN — delta cần thêm (dễ→khó), giá trị chống-bug
| # | Thêm gì | R | Effort | Giá trị |
|---|---|---|---|---|
| 1 | Task-type detector CLI (gói logic port/greenfield rải trong SKILL) | R1 | Dễ | Thấp (chỉ repackage) |
| **2** | **Validator cấu trúc GAP-QA** (đủ 3 rổ? 7 lens? mỗi câu có option+đề xuất+🔴/🟡+default? tách khách/dev?) | R2 | Dễ–vừa | **Cao** (gap-audit thành lặp được) |
| 3 | 7-lens coverage gate pre-build (mirror coverage_gate, đổi chiều) | R2/R3 | Vừa | Vừa |
| **4** | **Data-binding map + gate** (màn×element×{loại; data→nguồn/format/null}; ô data thiếu nguồn = fail) | R4 | Vừa | **Cao nhất** (đúng nơi bug migration trốn: LAND null, sai field) |
| 5 | Golden-record harness (wrap characterize_manifest + auto-capture màn) | R5 | Khó | Cao nhưng khó |
| 6 | Spec-table → test-case generator (bảng 13/14 tuần → case) | R3 | Khó nhất, dễ over-engineer | để CUỐI |

**Khuyến nghị (theo DP1 — đừng over-build):** làm **#4 + #2 trước** (giá trị cao, effort vừa, đánh đúng bug thật). Hoãn #5/#6. #1 tùy.

## ⚠️ Cần sửa trước khi build
`pinrich-cycle/SKILL.md` trỏ `~/Projects/port-harness/` nhưng path đó **KHÔNG tồn tại** trên máy này; script thật ở `~/Desktop/my-claude-skill/port-harness/`. → thống nhất 1 đường dẫn deploy trước khi thêm gate mới.

---

*Nguồn: phiên khám phá 2026-07 — chạy tay quy trình gap-hunt trên 売却活動報告書 (design Claude + spec) trong `gap-test-sales-report/`; + map đồ-có-sẵn vs R1–R5.*
