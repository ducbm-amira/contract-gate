# Legacy Behavior Manifest — /deal/example (fixture: pass-reordered)

Observable column is NOT last — column-reorder tolerance (D-05). The gate
must locate it by header text, not by fixed position.

| # | Observable | Hành vi | Loại | Đã port? |
|---|------------|---------|------|----------|
| 1 | DOM text `1,250万円` | Render giá 万円 có phẩy | visible | |
| 2 | click → URL khớp + query đúng | Card → /deal/property/:id | visible | |
| 3 | network POST /client_action_logs/owner_page_seen 1 lần + 1 row DB | Bắn ownerPageOpened khi mở | invisible side-effect | |
