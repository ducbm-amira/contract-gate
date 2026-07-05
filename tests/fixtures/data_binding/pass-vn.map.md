# Data-binding map — trang owner (VN headers, forgiving)

| Màn      | Phần tử        | Loại   | Nguồn (API/field/computed)          | Format      | Null/empty |
|----------|----------------|--------|-------------------------------------|-------------|------------|
| owner    |  Tên chủ nhà   | data   |  `GET /owner/:id` → `owner.name`    | raw         | "—" nếu null |
| owner    | 価格            | data   | `owner.sale.price`                  | 万円 (phẩy)  | ẩn dòng nếu null |
| owner    | Ảnh nhà        | image  |                                     |             |            |
| owner    | Nút 編集        | action |                                     |             |            |
| owner    | 面積            | computed | `land.area * 0.3025` (tsubo)      | `0.0` tsubo | 0 → "-"    |
