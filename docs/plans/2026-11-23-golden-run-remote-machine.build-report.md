# superlite build report

projection: fixed forecast saved at lint 2026-11-23T08:34:28 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.9      17.1  +10.2 (+147%)
agent cost (USD, +rework)      0.30      0.97  +0.67 (+226%)
task-minutes                  13.2       2.8  -10.4 (-79%)
agents                           2        11  +9 (+450%)
cost split: agents $0.74, rework $0.24, coordinator n/a, total $0.97
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (6.9 min)
model mix: sonnet 3 tasks $0.97
quality: tests 13603 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      6.9     0.8  -6.1 (-89%)     $0.254
T1    sonnet      6.3     0.7  -5.6 (-88%)     $0.368  first-time miss
T3    sonnet      n/a     1.3  n/a             $0.351  first-time miss

takeaway: ran 147% slower than projected; cost 226% over; biggest miss T2
