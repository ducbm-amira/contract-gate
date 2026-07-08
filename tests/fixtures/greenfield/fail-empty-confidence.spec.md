---
task: fail-empty-confidence-fixture
visual: bundle
---

# Greenfield Spec — fail-empty-confidence-fixture

Confidence column present but row 2's Confidence cell is blank — an
unstated confidence is itself an unresolved gap (D-06), rejected.

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0051 | DOM text `1,250,000` | 🟢 | |
| 2 | 見学 count excludes 問い合わせ rows | https://claude.ai/design/h/conf0052 | list column `見学` != `問い合わせ` value | | |
