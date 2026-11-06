# superlite build report

projection: fixed forecast saved at lint 2026-11-06T18:11:14

                         Projected    Actual  Delta
wall-clock (min)               2.3       9.8  +7.4 (+322%)
agent cost (USD, +rework)      0.31      1.26  +0.95 (+311%)
task-minutes                  10.8       3.6  -7.2 (-67%)
agents                           6         7  +1 (+17%)
cost split: agents $1.09, rework $0.16, coordinator n/a, total $1.26
concurrency: peak 3 at once (projected 6); critical path actual T3; projected T4 (2.3 min)
model mix: sonnet 6 tasks $1.26
quality: tests 21 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.7     0.3  -1.3 (-81%)     $0.105
T6    sonnet      1.6     0.3  -1.3 (-80%)     $0.105
T2    sonnet      1.7     0.4  -1.2 (-75%)     $0.136
T1    sonnet      1.6     0.4  -1.2 (-75%)     $0.136
T3    sonnet      1.9     0.9  -1.1 (-56%)     $0.434
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 322% slower than projected; cost 311% over; biggest miss T5
