# Legacy Behavior Manifest — /deal/example (fixture: fail-empty-observable)

Row 2 has a blank Observable cell, row 3 has a lone "-" — both should be
rejected as empty (D-04.3). The gate should name the first offending row.

| # | Hành vi | Loại | Observable (oracle để verify) | Đã port? |
|---|---------|------|-------------------------------|----------|
| 1 | Render giá 万円 có phẩy | visible | DOM text `1,250万円` | |
| 2 | Card → /deal/property/:id | visible |  | |
| 3 | empty/not-found state | edge-state | - | |
