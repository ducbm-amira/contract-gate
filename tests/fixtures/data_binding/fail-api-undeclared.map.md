# api column present but a data row leaves it blank → fail

| Screen | Element | Type | Source | API cũ/mới | Null |
|--------|---------|------|--------|-----------|------|
| owner | name  | data | `GET /owner/:id` → `name` | existing | "-" |
| owner | price | data | `sale.price` |  | 0 |
