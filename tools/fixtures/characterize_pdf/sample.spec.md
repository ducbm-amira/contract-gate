---
task: sample
visual: bundle
---

# Greenfield Spec — sample (fixture: characterize_pdf)

Fixture spec exercising `characterize_pdf.py` (05-02). Mixes `target: pdf`
and `target: web` rows — only the `pdf` rows are this adapter's job (D-07).
Row 2 (KPI number) is the one `extracted-wrong.txt` deliberately diverges on.

| # | Behavior | Design-ref | target | Observable |
|---|----------|-----------|--------|------------|
| 1 | Intro お問い合わせ copy renders in the PDF | ./mockup.html | pdf | お問い合わせ |
| 2 | KPI 閲覧数 (view count) value renders correctly | ./mockup.html | pdf | 1,250 |
| 3 | 契約日 date line matches YYYY-MM-DD shape | ./mockup.html | pdf | /契約日[:：]\s*\d{4}-\d{2}-\d{2}/ |
| 4 | Chart legend label renders (web-only, NOT this adapter's job) | ./mockup.html | web | DOM text 閲覧 present |
