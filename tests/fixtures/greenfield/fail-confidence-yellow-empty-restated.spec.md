---
task: fail-confidence-yellow-empty-restated-fixture
visual: bundle
---

# Greenfield Spec — fail-confidence-yellow-empty-restated-fixture

Row 2 is 🟡 (inferred) but the Restated cell is blank — the human never
weighed in on this row, so it must be rejected (D-06).

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0021 | DOM text `1,250,000` | 🟢 | |
| 2 | 見学 count excludes 問い合わせ rows | https://claude.ai/design/h/conf0022 | list column `見学` != `問い合わせ` value | 🟡 | |
