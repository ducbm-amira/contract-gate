# Data-binding map — search screen (EN headers)

| Screen | Element        | Type  | Source                        | Null/empty handling |
|--------|----------------|-------|-------------------------------|---------------------|
| search | result count   | data  | `POST /api/search` → `total`  | show 0              |
| search | station walk   | field | `listing.access[].walkMin`    | N/A — always set    |
| search | page title     | title |                               |                     |
