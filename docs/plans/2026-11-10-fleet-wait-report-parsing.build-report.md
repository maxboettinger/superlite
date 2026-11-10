# superlite build report

projection: fixed forecast saved at lint 2026-11-10T23:05:04 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.2      27.1  +23.9 (+751%)
agent cost (USD, +rework)      0.42      1.54  +1.12 (+268%)
task-minutes                   4.6       5.3  +0.7 (+14%)
agents                           3        12  +9 (+300%)
cost split: agents $1.06, rework $0.48, coordinator n/a, total $1.54
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T2 > T3 (3.2 min)
model mix: sonnet 3 tasks $1.54
quality: tests 5766 passed, 0 failed; first-time pass n/a; rework dispatches 5; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.8     2.4  +0.5 (+29%)     $0.583
T3    sonnet      1.4     1.7  +0.3 (+24%)     $0.375
T1    sonnet      1.4     1.2  -0.2 (-14%)     $0.581

takeaway: ran 751% slower than projected; cost 268% over; biggest miss T2
