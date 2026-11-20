# superlite build report

projection: fixed forecast saved at lint 2026-11-20T11:42:06 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              24.7      25.3  +0.6 (+2%)
agent cost (USD, +rework)      0.28      1.18  +0.90 (+327%)
task-minutes                  24.7       5.5  -19.3 (-78%)
agents                           2         7  +5 (+250%)
cost split: agents $0.82, rework $0.36, coordinator n/a, total $1.18
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (24.7 min)
model mix: sonnet 2 tasks $1.18
quality: tests 13315 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     12.4     1.8  -10.6 (-86%)    $0.242
T1    sonnet     12.4     3.7  -8.7 (-70%)     $0.936  first-time miss

takeaway: ran 2% slower than projected; cost 327% over; biggest miss T2
