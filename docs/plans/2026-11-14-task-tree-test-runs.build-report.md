# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:51:50 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              12.8     642.1  +629.3 (+4906%)
agent cost (USD, +rework)      0.27      2.51  +2.24 (+838%)
task-minutes                  19.0       5.8  -13.2 (-70%)
agents                           3        21  +18 (+600%)
cost split: agents $0.95, rework $1.56, coordinator n/a, total $2.51
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T2 > T3 (12.8 min)
model mix: sonnet 3 tasks $2.51
quality: tests 10004 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 8; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.1     0.6  -5.6 (-91%)     $0.596  first-time miss
T2    sonnet      6.1     0.7  -5.4 (-88%)     $0.204
T3    sonnet      6.7     4.5  -2.3 (-34%)     $1.708  first-time miss

takeaway: ran 4906% slower than projected; cost 838% over; biggest miss T1
