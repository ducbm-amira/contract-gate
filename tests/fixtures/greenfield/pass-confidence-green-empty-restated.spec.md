---
task: pass-confidence-green-fixture
visual: bundle
---

# Greenfield Spec — pass-confidence-green-fixture (fixture: pass-confidence-green-empty-restated)

Confidence column present, both rows marked 🟢 (sourced/certain) — Restated
stays empty and that is fine, since D-06 only requires Restated for rows
NOT marked 🟢.

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0001 | DOM text `1,250,000` | 🟢 | |
| 2 | KPI 閲覧数 value renders | https://claude.ai/design/h/conf0002 | pdftotext KPI row matches | 🟢 | |
