# superlite build report

projection: fixed forecast saved at lint 2026-11-12T23:16:58

                         Projected    Actual  Delta
wall-clock (min)              10.0       9.2  -0.8 (-8%)
agent cost (USD, +rework)      0.47      1.33  +0.86 (+183%)
task-minutes                  37.6       4.6  -33.0 (-88%)
agents                           4         8  +4 (+100%)
cost split: agents $0.93, rework $0.39, coordinator n/a, total $1.33
concurrency: peak 3 at once (projected 4); critical path actual T4; projected T3 (10.0 min)
model mix: sonnet 4 tasks $1.33
quality: tests 8084 passed, 0 failed; first-time pass 1/4 (25%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.3     0.7  -8.6 (-92%)     $0.155
T4    sonnet      9.0     0.7  -8.3 (-92%)     $0.272  first-time miss
T3    sonnet     10.0     1.7  -8.2 (-82%)     $0.436  first-time miss
T2    sonnet      9.3     1.4  -7.9 (-84%)     $0.463  first-time miss

takeaway: ran 8% faster than projected; cost 183% over; biggest miss T1
