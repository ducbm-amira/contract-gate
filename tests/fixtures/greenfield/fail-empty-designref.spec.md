---
task: fail-empty-designref-fixture
visual: bundle
---

# Greenfield Spec — fail-empty-designref-fixture (fixture: fail-empty-designref)

Non-exempt spec (`visual: bundle`). Row 2 has a blank Design-ref cell — a
blank Design-ref is NEVER treated as exempt on its own (D-04: exempt only
when explicit). The gate should name the offending row.

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Intro copy renders | https://claude.ai/design/h/faildref01 | web | DOM text present |
| 2 | KPI value renders | | web | DOM text present |
