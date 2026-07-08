---
task: pass-confidence-yellow-fixture
visual: bundle
---

# Greenfield Spec — pass-confidence-yellow-fixture (fixture: pass-confidence-yellow-with-restated)

Row 2 is 🟡 (inferred) and carries a Restated cell in the human's own
words, distinct from the Design-ref/Observable text — this is the intended
D-06 pass shape.

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0011 | DOM text `1,250,000` | 🟢 | |
| 2 | 見学 count excludes 問い合わせ rows | https://claude.ai/design/h/conf0012 | list column `見学` != `問い合わせ` value | 🟡 | I checked the list screenshot myself: 見学 and 問い合わせ show different numbers on the same row, so they must be counted separately, not derived from each other |
