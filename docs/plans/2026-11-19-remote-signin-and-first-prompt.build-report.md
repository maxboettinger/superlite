# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:32:39 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.7       2.2  -1.5 (-41%)
agent cost (USD, +rework)      0.39      1.11  +0.72 (+184%)
task-minutes                  13.6       3.9  -9.7 (-71%)
agents                           4        11  +7 (+175%)
cost split: agents $1.11, rework $0.00, coordinator n/a, total $1.11
concurrency: peak 4 at once (projected 4); critical path actual T4; projected T3 (3.7 min)
model mix: sonnet 4 tasks $1.11
quality: tests 12209 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T3    sonnet      3.7     0.7  -3.0 (-81%)     $0.196
T2    sonnet      3.3     0.7  -2.6 (-78%)     $0.231
T1    sonnet      3.3     1.1  -2.2 (-66%)     $0.311
T4    sonnet      3.3     1.3  -1.9 (-59%)     $0.370

takeaway: ran 41% faster than projected; cost 184% over; biggest miss T3
