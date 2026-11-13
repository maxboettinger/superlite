# superlite build report

projection: fixed forecast saved at lint 2026-11-13T04:16:44 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.0      20.0  +13.0 (+186%)
agent cost (USD, +rework)      0.52      1.93  +1.42 (+275%)
task-minutes                  20.7       6.5  -14.2 (-69%)
agents                           6        19  +13 (+217%)
cost split: agents $1.41, rework $0.52, coordinator n/a, total $1.93
concurrency: peak 4 at once (projected 4); critical path actual T2 T3; projected T3 > T2 (7.0 min)
model mix: sonnet 6 tasks $1.93
quality: tests 8800 passed, 0 failed; first-time pass 3/6 (50%); rework dispatches 5; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      3.9     1.1  -2.9 (-73%)     $0.444  first-time miss
T6    sonnet      3.7     1.0  -2.7 (-73%)     $0.271
T1    sonnet      3.9     1.4  -2.5 (-64%)     $0.484  first-time miss
T5    sonnet      3.0     0.8  -2.2 (-73%)     $0.180
T4    sonnet      3.0     0.8  -2.2 (-72%)     $0.188
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 186% slower than projected; cost 275% over; biggest miss T3
