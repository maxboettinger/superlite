# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:58:11 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              18.6      12.1  -6.6 (-35%)
agent cost (USD, +rework)      0.53      1.26  +0.73 (+136%)
task-minutes                  30.8       4.6  -26.2 (-85%)
agents                           5        12  +7 (+140%)
cost split: agents $0.98, rework $0.28, coordinator n/a, total $1.26
concurrency: peak 3 at once (projected 3); critical path actual T1 T2; projected T1 > T2 > T5 (18.6 min)
model mix: sonnet 5 tasks $1.26
quality: tests 10067 passed, 0 failed; first-time pass 3/5 (60%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      6.1     0.6  -5.6 (-91%)     $0.154
T1    sonnet      6.3     0.8  -5.5 (-88%)     $0.263  first-time miss
T4    sonnet      6.0     0.6  -5.5 (-90%)     $0.154
T5    sonnet      6.1     0.8  -5.4 (-88%)     $0.201
T2    sonnet      6.2     2.0  -4.2 (-68%)     $0.489  first-time miss

takeaway: ran 35% faster than projected; cost 136% over; biggest miss T3
