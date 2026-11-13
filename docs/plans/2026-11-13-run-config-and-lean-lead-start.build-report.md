# superlite build report

projection: fixed forecast saved at lint 2026-11-13T00:50:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.3       9.0  -1.3 (-13%)
agent cost (USD, +rework)      0.56      1.37  +0.80 (+142%)
task-minutes                  29.4       5.2  -24.1 (-82%)
agents                           6         9  +3 (+50%)
cost split: agents $1.28, rework $0.09, coordinator n/a, total $1.37
concurrency: peak 4 at once (projected 4); critical path actual T1 T5; projected T1 > T3 (10.3 min)
model mix: sonnet 6 tasks $1.37
quality: tests 8362 passed, 0 failed; first-time pass 5/6 (83%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.6     1.1  -4.6 (-81%)     $0.231
T2    sonnet      5.5     1.4  -4.1 (-74%)     $0.343
T4    sonnet      4.5     0.4  -4.0 (-90%)     $0.132
T5    sonnet      4.6     0.7  -3.9 (-84%)     $0.280  first-time miss
T6    sonnet      4.5     0.7  -3.8 (-85%)     $0.159
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 13% faster than projected; cost 142% over; biggest miss T1
