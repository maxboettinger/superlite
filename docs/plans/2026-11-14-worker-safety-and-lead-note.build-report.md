# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:18:11

                         Projected    Actual  Delta
wall-clock (min)               7.7       6.9  -0.8 (-10%)
agent cost (USD, +rework)      0.34      0.65  +0.30 (+88%)
task-minutes                  37.9       2.2  -35.7 (-94%)
agents                           5         8  +3 (+60%)
cost split: agents $0.56, rework $0.08, coordinator n/a, total $0.65
concurrency: peak 3 at once (projected 5); critical path actual T3; projected T2 (7.7 min)
model mix: sonnet 5 tasks $0.65
quality: tests 9959 passed, 0 failed; first-time pass 4/5 (80%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      7.6     0.4  -7.2 (-95%)     $0.096
T1    sonnet      7.5     0.4  -7.2 (-95%)     $0.096
T2    sonnet      7.7     0.5  -7.2 (-94%)     $0.149
T5    sonnet      7.6     0.5  -7.1 (-94%)     $0.112
T3    sonnet      7.5     0.5  -7.1 (-93%)     $0.196  first-time miss

takeaway: ran 10% faster than projected; cost 88% over; biggest miss T4
