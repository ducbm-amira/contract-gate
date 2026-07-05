---
task: pass-no-visual-exempt-fixture
visual: none
---

# Greenfield Spec — pass-no-visual-exempt-fixture (fixture: pass-no-visual-exempt)

Pure logic/artifact task, no mockup. `visual: none` exempts the Design-ref
layer for every row (D-04) — Design-ref cells are blank or the `N/A-logic`
sentinel, but Observable stays mandatory and IS populated for every row.

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Compute activity totals correctly | | logic | sum(rows) == expected total |
| 2 | Round distance to meters (徒歩 phút) | N/A-logic | logic | ceil(distance/80) == legacy value |
