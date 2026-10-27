# superlite build report

projection: fixed forecast saved at lint 2026-10-27T15:28:15 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              11.5      24.6  +13.1 (+113%)
agent cost (USD, +rework)      0.74      3.88  +3.14 (+422%)
task-minutes                  39.6      30.6  -9.0 (-23%)
agents                           8        22  +14 (+175%)
cost split: agents $3.88, rework $0.00, coordinator $10.81, total $14.69
concurrency: peak 7 at once (projected 7); critical path actual T4 T8 T9; projected T4 > T8 (11.5 min)
model mix: haiku 2 tasks $0.37, sonnet 8 tasks $3.51, coordinator opus $10.81
quality: tests 20 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 43

task  model      pred  actual  delta             cost
T3    sonnet      5.6     2.1  -3.5 (-62%)     $0.270
T7    sonnet      5.5     2.4  -3.1 (-56%)     $0.324
T5    sonnet      5.6     2.8  -2.8 (-50%)     $0.360
T8    sonnet      5.6     3.2  -2.5 (-44%)     $0.480
T2    haiku       2.8     4.7  +1.8 (+65%)     $0.340
(+5 smaller misses; `sl report --json` lists all)

takeaway: ran 113% slower than projected; cost 422% over; biggest miss T3
