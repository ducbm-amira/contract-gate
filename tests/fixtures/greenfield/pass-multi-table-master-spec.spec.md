---
task: pass-multi-table-fixture
visual: bundle
---

# Master spec — 2 screens, D-07

## Màn 1: report-1

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Chọn property card | https://claude.ai/design/h/multi01 | click -> goReport2() | 🟢 | |

## Màn 2: report-2

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Thiếu field vẫn cho qua | https://claude.ai/design/h/multi02 | goReport3() luôn true | 🟡 | tự đọc source xác nhận không có check nào |
