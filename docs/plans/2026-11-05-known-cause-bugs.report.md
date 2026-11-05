# superlite build report

projection: fixed forecast saved at lint 2026-11-05T13:34:36 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.9      17.0  +11.0 (+186%)
agent cost (USD, +rework)      1.02      2.29  +1.27 (+124%)
task-minutes                  25.0      27.5  +2.5 (+10%)
agents                          14        15  +1 (+7%)
cost split: agents $2.01, rework $0.28, coordinator $6.46 (74 turns, context median 306.3k, peak 341.4k; session $10.42), total $8.75
concurrency: peak 7 at once (projected 10); critical path actual T3 T4; projected T1 > T2 > T14 (5.9 min)
model mix: haiku 2 tasks $0.03, sonnet 12 tasks $2.26, coordinator opus $6.46
quality: tests 2640 passed, 0 failed; first-time pass 11/14 (78%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T8    haiku       1.6     2.6  +1.1 (+69%)     $0.016  first-time miss
T2    sonnet      2.0     0.9  -1.0 (-53%)     $0.238  first-time miss
T13   sonnet      2.0     2.8  +0.9 (+44%)     $0.194
T12   haiku       1.6     2.4  +0.8 (+52%)     $0.013
T1    sonnet      2.1     2.7  +0.6 (+31%)     $0.245
(+9 smaller misses; `sl report --json` lists all)

takeaway: ran 186% slower than projected; cost 124% over; biggest miss T8
