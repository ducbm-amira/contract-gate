# Data-binding map — 売却活動報告書 (sandbox dogfood of contract-gate #4)

> Screen × Element × {type; source; format; null}. Chỉ liệt kê element **có
> data** + vài static để đối chiếu (DP1 — không map 80% chrome hiển nhiên).
> Ô loại `data` chưa ghi nguồn / thiếu null-handling ⇒ gate `fail`.

<!-- data-binding:start -->
| Screen | Element | Type | Source (API/field/computed) | Format | Null/empty |
|--------|---------|------|------------------------------|--------|------------|
| report-9 顧客情報 | 会社名 | data | `company.name` (company state) | raw | "" → placeholder |
| report-9 顧客情報 | 顧客名+敬称 | data | `customer.name` + `customer.honorific` | `{name} {様}` | 敬称 null → 様 |
| report-5 媒体サマリー | 掲載期間(週) | computed | `weeksBetween(contractStart, today)` | `N週目` | contractStart null → grayout |
| report-5 媒体サマリー | 反響数 | data | `POST /report/media` → `media[].inquiries` | integer | 0 表示 |
| report-8 AI文 | 物件名 | data | `sale_.property_name` | raw | — nếu null |
| report-8 AI文 | 面積 | data | `sale_.land_area` | `0.0㎡` | LAND null → "-" |
| report-1 表紙 | タイトル | title | | | |
<!-- data-binding:end -->
