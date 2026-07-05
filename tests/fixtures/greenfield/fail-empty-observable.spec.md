---
task: fail-empty-observable-fixture
visual: bundle
---

# Greenfield Spec — fail-empty-observable-fixture (fixture: fail-empty-observable)

Row 2 has a blank Observable cell — must be rejected (Observable is
mandatory ALWAYS, even with a valid Design-ref). The gate should name the
offending row.

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Intro copy renders | https://claude.ai/design/h/failobs01 | web | DOM text present |
| 2 | KPI value renders | https://claude.ai/design/h/failobs02 | pdf | |
