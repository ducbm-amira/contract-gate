# Golden-record — header-needle collision regression (GOLD-06)

> Same tricky header as pass-header-collision.map.md, but Expected and
> Actual genuinely disagree. Before GOLD-06 this silently PASSED (actual_col
> pointed back at the Expected column, comparing it to itself). Must FAIL,
> naming both real values.

| Record | Field | Expected (DB thật, viết đúng dạng hiển thị) | Actual (UI thật) |
|--------|-------|-----------------------------------------------|-------------------|
| p1 | price | ¥29,880,000 | ¥30,000,000 |
