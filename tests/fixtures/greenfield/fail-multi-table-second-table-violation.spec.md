---
task: fail-multi-table-second-table-fixture
visual: bundle
---

# Master spec — 3 screens, second and third tables violate D-06

## Màn 1: report-1

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Chọn property card | https://claude.ai/design/h/mfail01 | click -> goReport2() | 🟢 | |

## Màn 2: report-2

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | 種別 required nhưng không chặn thật | https://claude.ai/design/h/mfail02 | goReport3() không check 種別 | 🔴 | |

## Màn 3: report-3

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Thiếu field vẫn cho qua (warn-only) | https://claude.ai/design/h/mfail03 | goReport4() luôn true | 🟡 | |
