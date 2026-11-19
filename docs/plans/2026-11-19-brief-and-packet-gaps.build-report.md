# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:13:47 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.7      46.3  +36.5 (+375%)
agent cost (USD, +rework)      0.30      1.21  +0.91 (+299%)
task-minutes                  28.3       3.2  -25.1 (-89%)
agents                           3        20  +17 (+567%)
cost split: agents $0.64, rework $0.58, coordinator n/a, total $1.21
concurrency: peak 3 at once (projected 3); critical path actual T3; projected T3 (9.7 min)
model mix: sonnet 3 tasks $1.21
quality: tests 12610 passed, 0 failed; first-time pass 0/3 (0%); rework dispatches 6; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      9.7     1.1  -8.7 (-89%)     $0.511  first-time miss
T1    sonnet      9.3     1.1  -8.2 (-88%)     $0.305  first-time miss
T2    sonnet      9.2     1.1  -8.2 (-88%)     $0.398  first-time miss

takeaway: ran 375% slower than projected; cost 299% over; biggest miss T3
