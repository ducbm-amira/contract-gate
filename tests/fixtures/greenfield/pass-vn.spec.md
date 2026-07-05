---
task: pass-vn-fixture
visual: bundle
---

# Greenfield Spec — pass-vn-fixture (fixture: pass-vn)

Bảng hành vi theo mẫu canonical (05-01 PLAN). Observable và Design-ref của
các dòng dưới cố tình có khoảng trắng dư, văn xuôi tiếng Việt, và dấu câu
full-width để khớp trường hợp pass-forgiving (D-01) — mục tiêu của gate là
bắt cell RỖNG/KHÔNG-resolvable, không phải lint markdown.

| # | Hành vi | Design-ref | target | Observable (assertion) |
|---|---------|-----------|--------|-------------------------|
| 1 |   Render giá 万円 có phẩy   | https://claude.ai/design/h/vn0001abc   | web |   DOM text `1,250万円`   |
| 2 | Card → /deal/property/:id | https://claude.ai/design/h/vn0002def | web | click → URL khớp　và query đúng đấy，đúng luôn |
