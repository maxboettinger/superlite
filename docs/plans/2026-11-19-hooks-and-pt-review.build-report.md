# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:53:12 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.9      19.4  +12.5 (+181%)
agent cost (USD, +rework)      0.38      1.69  +1.32 (+350%)
task-minutes                  25.7      11.4  -14.3 (-56%)
agents                           4        16  +12 (+300%)
cost split: agents $1.53, rework $0.16, coordinator n/a, total $1.69
concurrency: peak 4 at once (projected 4); critical path actual T3; projected T3 (6.9 min)
model mix: haiku 1 tasks $0.01, sonnet 5 tasks $1.68
quality: tests 12271 passed, 0 failed; first-time pass 3/6 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      6.3     1.1  -5.2 (-83%)     $0.221
T3    sonnet      6.9     2.5  -4.5 (-64%)     $0.785  first-time miss
T2    sonnet      6.4     2.3  -4.0 (-63%)     $0.218  first-time miss
T1    haiku       6.1     3.2  -2.9 (-48%)     $0.014  first-time miss
T5    sonnet      n/a     1.7  n/a             $0.343
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 181% slower than projected; cost 350% over; biggest miss T4
