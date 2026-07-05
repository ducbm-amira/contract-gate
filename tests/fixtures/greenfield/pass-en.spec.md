---
task: pass-en-fixture
visual: bundle
---

# Greenfield Spec — pass-en-fixture (fixture: pass-en)

EN header variant (canonical column names) — proves header text is not
locale-locked (D-01).

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Render price with thousand separator | https://claude.ai/design/h/en0001xyz | web | DOM text `1,250,000` |
| 2 | KPI 閲覧数 value renders | https://claude.ai/design/h/en0002xyz | pdf | pdftotext KPI row == fetched value |
