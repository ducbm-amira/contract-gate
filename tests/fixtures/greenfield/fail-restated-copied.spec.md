---
task: fail-restated-copied-fixture
visual: bundle
---

# Greenfield Spec — fail-restated-copied-fixture

Row 2 is 🟡 and Restated is a verbatim copy of the Observable cell — this
is a human pasting the AI's own text back, not re-deriving it in their own
words, and must be rejected (D-06).

| # | Behavior | Design-ref | Observable | Confidence | Restated |
|---|----------|-----------|------------|------------|----------|
| 1 | Price renders with thousand separator | https://claude.ai/design/h/conf0031 | DOM text `1,250,000` | 🟢 | |
| 2 | 見学 count excludes 問い合わせ rows | https://claude.ai/design/h/conf0032 | list column `見学` != `問い合わせ` value | 🟡 | list column `見学` != `問い合わせ` value |
