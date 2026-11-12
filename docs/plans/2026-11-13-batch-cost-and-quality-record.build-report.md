# superlite build report

projection: fixed forecast saved at lint 2026-11-13T00:14:24 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.1      10.5  +0.4 (+4%)
agent cost (USD, +rework)      1.09      2.46  +1.36 (+124%)
task-minutes                  43.1      10.3  -32.8 (-76%)
agents                           9        14  +5 (+56%)
cost split: agents $2.15, rework $0.31, coordinator n/a, total $2.46
concurrency: peak 7 at once (projected 8); critical path actual T2 T9; projected T7 > T9 (10.1 min)
model mix: sonnet 9 tasks $2.46
quality: tests 8271 passed, 0 failed; first-time pass 3/9 (33%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T7    sonnet      5.3     1.0  -4.4 (-82%)     $0.264  first-time miss
T1    sonnet      4.7     0.6  -4.1 (-86%)     $0.154
T6    sonnet      4.7     0.7  -4.0 (-85%)     $0.178
T2    sonnet      4.8     0.8  -3.9 (-82%)     $0.301  first-time miss
T8    sonnet      4.5     0.6  -3.9 (-86%)     $0.154
(+4 smaller misses; `sl report --json` lists all)

takeaway: ran 4% slower than projected; cost 124% over; biggest miss T7
