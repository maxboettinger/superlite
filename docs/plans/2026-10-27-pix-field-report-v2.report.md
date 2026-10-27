# superlite build report

projection: fixed forecast saved at lint 2026-10-26T10:24:09 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.8       6.0  +0.1 (+2%)
agent cost (USD, +rework)      0.38      2.26  +1.88 (+489%)
task-minutes                  15.3      19.6  +4.3 (+28%)
agents                           4        11  +7 (+175%)
cost split: agents $2.20, rework $0.06, coordinator $5.74, total $8.01
concurrency: peak 6 at once (projected 4); critical path actual T1 T2; projected T2 (5.8 min)
model mix: sonnet 9 tasks $2.20, unknown 1 tasks $0.06, coordinator opus $5.74
quality: tests 959 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 27

task  model      pred  actual  delta             cost
T2    sonnet      5.8     1.4  -4.4 (-76%)     $0.197
T1    sonnet      3.2     6.0  +2.9 (+90%)     $0.559
T3    sonnet      3.1     1.3  -1.8 (-58%)     $0.170
T4    sonnet      3.2     1.6  -1.6 (-50%)     $0.189
T10   sonnet      n/a     1.4  n/a             $0.118
(+5 smaller misses; `sl report --json` lists all)

takeaway: ran 2% slower than projected; cost 489% over; biggest miss T2
