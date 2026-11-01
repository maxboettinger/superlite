# superlite build report

projection: fixed forecast saved at lint 2026-11-01T14:09:31 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              17.8       8.5  -9.3 (-52%)
agent cost (USD, +rework)      0.97      3.70  +2.73 (+281%)
task-minutes                  41.7      21.9  -19.8 (-48%)
agents                           7        12  +5 (+71%)
cost split: agents $3.35, rework $0.35, coordinator $8.53, total $12.24
concurrency: peak 5 at once (projected 5); critical path actual T6 T7 T8; projected T3 > T6 > T7 (17.8 min)
model mix: sonnet 7 tasks $3.35, unknown 1 tasks $0.35, coordinator opus $8.53
quality: tests 1156 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 79

task  model      pred  actual  delta             cost
T1    ?           5.5     0.0  -5.5 (-100%)    $0.352
T5    sonnet      5.9     2.1  -3.8 (-64%)     $0.299
T6    sonnet      8.3     4.6  -3.7 (-45%)     $0.724
T7    sonnet      5.4     2.4  -3.0 (-56%)     $0.377
T3    sonnet      4.1     1.6  -2.5 (-61%)     $0.161
(+3 smaller misses; `sl report --json` lists all)

takeaway: ran 52% faster than projected; cost 281% over; biggest miss T1
