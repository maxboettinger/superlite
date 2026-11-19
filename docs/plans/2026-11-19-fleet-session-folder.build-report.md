# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:14:18 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              21.5      10.2  -11.3 (-52%)
agent cost (USD, +rework)      0.30      0.72  +0.41 (+137%)
task-minutes                  32.3      10.5  -21.7 (-67%)
agents                           3         8  +5 (+167%)
cost split: agents $0.72, rework $0.00, coordinator n/a, total $0.72
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T3 (21.5 min)
model mix: sonnet 3 tasks $0.72
quality: tests 12612 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet     10.7     0.3  -10.4 (-97%)    $0.082  first-time miss
T2    sonnet     10.7     0.5  -10.2 (-95%)    $0.156
T1    sonnet     10.8     9.7  -1.2 (-11%)     $0.478  first-time miss

takeaway: ran 52% faster than projected; cost 137% over; biggest miss T3
