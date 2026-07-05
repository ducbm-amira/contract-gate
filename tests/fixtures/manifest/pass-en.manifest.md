# Legacy Behavior Manifest — /deal/example (fixture: pass-en)

EN header variant — column names differ from the canonical VN table but the
Observable column is still recognizable by header substring match (D-05).

| # | Behavior | Type | Observable | Ported? |
|---|----------|------|------------|---------|
| 1 | Render price with thousand separator | visible | DOM text `1,250,000` | |
| 2 | Card click navigates to detail page | visible | click -> URL matches route + query | |
| 3 | Fires analytics event on page open | invisible side-effect | network POST /events fired once | |
