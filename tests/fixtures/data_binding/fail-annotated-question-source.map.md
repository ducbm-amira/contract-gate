# Data-binding map — a data source annotated with `? reason` is still unresolved

| Screen | Element    | Type | Source                        | Null/empty |
|--------|------------|------|-------------------------------|------------|
| owner  | owner name | data | `owner.name`                  | "-"        |
| owner  | price      | data | ? (sale_ column not in spec)  | 0          |
