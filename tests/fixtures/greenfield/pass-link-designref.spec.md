---
task: pass-link-designref-fixture
visual: bundle
---

# Greenfield Spec — pass-link-designref-fixture (fixture: pass-link-designref)

Design-ref is a `.../design/h/<code>` Claude Design link — must pass on
format alone (non-empty), never curled (D-03, no-network preserved).

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Intro 問い合わせ copy renders | https://claude.ai/design/h/abcXYZ123 | pdf | pdftotext contains "お問い合わせ" |
