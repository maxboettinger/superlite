# superlite build report

projection: fixed forecast saved at lint 2026-11-13T06:42:44 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.6       3.1  -7.6 (-71%)
agent cost (USD, +rework)      0.43      0.66  +0.23 (+53%)
task-minutes                  16.6       3.0  -13.6 (-82%)
agents                           5         6  +1 (+20%)
cost split: agents $0.66, rework $0.00, coordinator n/a, total $0.66
concurrency: peak 2 at once (projected 2); critical path actual T1 T3 T5; projected T1 > T4 > T5 (10.6 min)
model mix: sonnet 5 tasks $0.66
quality: tests 9101 passed, 0 failed; first-time pass 4/5 (80%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      4.2     0.3  -4.0 (-94%)     $0.082
T4    sonnet      3.1     0.5  -2.6 (-85%)     $0.117
T1    sonnet      3.3     0.7  -2.6 (-78%)     $0.166
T3    sonnet      3.1     0.7  -2.3 (-76%)     $0.132
T2    sonnet      2.9     0.8  -2.1 (-73%)     $0.160  first-time miss

takeaway: ran 71% faster than projected; cost 53% over; biggest miss T5
