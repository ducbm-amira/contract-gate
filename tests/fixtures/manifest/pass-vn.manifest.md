# Legacy Behavior Manifest — /deal/example (fixture: pass-vn)

Bảng hành vi theo mẫu thật ở `skills/sdd-port-page/SKILL.md` (P1 output).
Observable của các dòng dưới cố tình có khoảng trắng dư, văn xuôi tiếng
Việt, và dấu câu full-width để khớp trường hợp pass-forgiving (D-05) —
mục tiêu của gate là bắt Observable RỖNG, không phải lint markdown.

| # | Hành vi | Loại | Observable (oracle để verify) | Đã port? |
|---|---------|------|-------------------------------|----------|
| 1 |   Render giá 万円 có phẩy   | visible |   DOM text `1,250万円`   | |
| 2 | Card → /deal/property/:id | visible | click → URL khớp　và query đúng đấy，đúng luôn | |
| 3 | Bắn `ownerPageOpened` khi mở (nếu `!fromOwnerPage`) | invisible side-effect | network `POST /client_action_logs/owner_page_seen` 1 lần + 1 row DB | |
| 4 | 徒歩 phút = ceil(distance/80) | derivation | giá trị tính ≡ legacy với cùng input（đầy đủ） | |
| 5 | empty/not-found state | edge-state | DOM đúng wrapper, không trắng trang。 | |
