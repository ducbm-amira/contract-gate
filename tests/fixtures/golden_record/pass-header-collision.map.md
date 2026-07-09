# Golden-record — header-needle collision regression (GOLD-06)

> Expected's own header text contains "hiển thị" (a VN needle for Actual),
> which used to make `_find_col` resolve actual_col back onto the Expected
> column itself. With GOLD-06's exclude fix, actual_col must resolve to the
> real Actual column instead — proven here by a row where Expected and
> Actual genuinely match.

| Record | Field | Expected (DB thật, viết đúng dạng hiển thị) | Actual (UI thật) |
|--------|-------|-----------------------------------------------|-------------------|
| p1 | price | ¥29,880,000 | ¥29,880,000 |
