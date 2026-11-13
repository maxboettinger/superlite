# superlite build report

projection: fixed forecast saved at lint 2026-11-13T09:54:01

                         Projected    Actual  Delta
wall-clock (min)               7.6       2.8  -4.8 (-63%)
agent cost (USD, +rework)      0.30      0.57  +0.27 (+88%)
task-minutes                  11.3       3.1  -8.2 (-73%)
agents                           3         5  +2 (+67%)
cost split: agents $0.57, rework $0.00, coordinator n/a, total $0.57
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T3 (7.6 min)
model mix: sonnet 3 tasks $0.57
quality: tests 9615 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.7     0.8  -3.0 (-80%)     $0.141
T3    sonnet      3.7     0.9  -2.8 (-77%)     $0.165
T1    sonnet      3.9     1.5  -2.4 (-62%)     $0.262

takeaway: ran 63% faster than projected; cost 88% over; biggest miss T2
