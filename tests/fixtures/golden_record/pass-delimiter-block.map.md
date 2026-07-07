# Golden-record — delimiter restricts scope

Some prose describing the task, followed by a BROKEN table outside the
delimiter block (mismatched Expected/Actual on purpose) that must be ignored:

| Record | Field | Expected | Actual |
|--------|-------|----------|--------|
| broken-1 | x | 100 | 999 |

The real golden-record block:

<!-- golden-record:start -->
| Record | Field | Expected | Actual |
|--------|-------|----------|--------|
| owner-400 | 駅徒歩 | 徒歩5分 | 徒歩5分 |
<!-- golden-record:end -->
