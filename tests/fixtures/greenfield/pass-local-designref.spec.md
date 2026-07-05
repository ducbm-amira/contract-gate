---
task: pass-local-designref-fixture
visual: bundle
---

# Greenfield Spec — pass-local-designref-fixture (fixture: pass-local-designref)

Design-ref points at a sibling local mockup file that exists on disk
(`./mockup-sample.html`) — D-03 local-path resolvable.

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Mockup section renders | ./mockup-sample.html | web | DOM text "Sample mockup" |
