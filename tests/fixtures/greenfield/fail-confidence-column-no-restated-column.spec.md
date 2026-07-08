---
task: fail-confidence-no-restated-column-fixture
visual: bundle
---

# Greenfield Spec — fail-confidence-no-restated-column-fixture

Header carries a Confidence column but no Restated/Human column anywhere
— a schema error (D-06), rejected before any row is even inspected.

| # | Behavior | Design-ref | Observable | Confidence |
|---|----------|-----------|------------|------------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0041 | DOM text `1,250,000` | 🟢 |
