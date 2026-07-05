---
task: fail-designref-missing-path-fixture
visual: bundle
---

# Greenfield Spec — fail-designref-missing-path-fixture (fixture: fail-designref-missing-path)

Design-ref is a local path that does NOT exist on disk relative to this
spec's directory — must fail (D-03 resolvability).

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Mockup section renders | ./does-not-exist.html | web | DOM text present |
