# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:03:05

                         Projected    Actual  Delta
wall-clock (min)              24.0      55.7  +31.7 (+132%)
agent cost (USD, +rework)      0.47      1.53  +1.07 (+229%)
task-minutes                  47.1       6.2  -40.8 (-87%)
agents                           6        18  +12 (+200%)
cost split: agents $1.00, rework $0.53, coordinator n/a, total $1.53
concurrency: peak 4 at once (projected 3); critical path actual T4; projected T1 > T3 > T5 (24.0 min)
model mix: sonnet 6 tasks $1.53
quality: tests 7470 passed, 0 failed; first-time pass 2/6 (33%); rework dispatches 6; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      7.5     0.4  -7.1 (-94%)     $0.285  first-time miss
T3    sonnet      7.8     0.8  -7.0 (-90%)     $0.232  first-time miss
T2    sonnet      7.8     0.8  -7.0 (-90%)     $0.135
T4    sonnet      7.8     0.9  -6.9 (-89%)     $0.290  first-time miss
T6    sonnet      7.6     0.9  -6.7 (-89%)     $0.139
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 132% slower than projected; cost 229% over; biggest miss T5
