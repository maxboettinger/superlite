# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:59:51 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              18.8      14.0  -4.8 (-25%)
agent cost (USD, +rework)      0.30      0.89  +0.59 (+195%)
task-minutes                  28.0       3.6  -24.4 (-87%)
agents                           3         9  +6 (+200%)
cost split: agents $0.62, rework $0.27, coordinator n/a, total $0.89
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T2 > T3 (18.8 min)
model mix: sonnet 3 tasks $0.89
quality: tests 9390 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 3; open incidents 2

task  model      pred  actual  delta             cost
T2    sonnet      9.7     1.5  -8.3 (-85%)     $0.326  first-time miss
T3    sonnet      9.1     0.8  -8.3 (-91%)     $0.346  first-time miss
T1    sonnet      9.2     1.3  -7.9 (-86%)     $0.219

takeaway: ran 25% faster than projected; cost 195% over; biggest miss T2
