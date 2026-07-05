---
task: pass-reordered-fixture
visual: bundle
---

# Greenfield Spec — pass-reordered-fixture (fixture: pass-reordered)

Observable and Design-ref columns are NOT in canonical order — column-reorder
tolerance (D-01). The gate must locate both by header text, not by fixed
position.

| # | Observable | Behavior | target | Design-ref |
|---|------------|----------|--------|-----------|
| 1 | DOM text `1,250万円` | Render giá 万円 có phẩy | web | https://claude.ai/design/h/reorder01 |
| 2 | click → URL khớp + query đúng | Card → /deal/property/:id | web | https://claude.ai/design/h/reorder02 |
