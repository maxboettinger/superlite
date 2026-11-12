# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:49:20 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              11.8      29.0  +17.2 (+146%)
agent cost (USD, +rework)      0.34      1.21  +0.87 (+260%)
task-minutes                  33.2       3.3  -29.8 (-90%)
agents                           3        12  +9 (+300%)
cost split: agents $0.75, rework $0.46, coordinator n/a, total $1.21
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T1 (11.8 min)
model mix: sonnet 3 tasks $1.21
quality: tests 7470 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 5; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     10.9     0.8  -10.1 (-93%)    $0.281  first-time miss
T3    sonnet     10.5     0.5  -10.0 (-95%)    $0.111
T1    sonnet     11.8     2.0  -9.8 (-83%)     $0.816  first-time miss

takeaway: ran 146% slower than projected; cost 260% over; biggest miss T2
