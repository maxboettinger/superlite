# superlite build report

projection: fixed forecast saved at lint 2026-11-23T19:30:28 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.4      17.0  +8.6 (+103%)
agent cost (USD, +rework)      0.26      1.73  +1.48 (+569%)
task-minutes                  16.1       3.3  -12.9 (-80%)
agents                           2         7  +5 (+250%)
cost split: agents $0.63, rework $1.10, coordinator n/a, total $1.73
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (8.4 min)
model mix: sonnet 2 tasks $1.73
quality: tests 13638 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      8.4     1.9  -6.5 (-78%)     $0.323
T2    sonnet      7.8     1.4  -6.4 (-82%)     $1.411  first-time miss

takeaway: ran 103% slower than projected; cost 569% over; biggest miss T1
