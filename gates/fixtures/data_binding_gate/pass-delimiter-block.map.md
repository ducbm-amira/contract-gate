# Doc with an unrelated table OUTSIDE the delimiter

This first table has type + source columns but a broken data row — it MUST be
ignored because it is outside the data-binding block.

| Type | Source | Element |
|------|--------|---------|
| data |        | orphan  |

<!-- data-binding:start -->
| Screen | Element | Type | Source              | Null/empty |
|--------|---------|------|---------------------|------------|
| map    | price   | data | `unit.price`        | hide       |
<!-- data-binding:end -->
