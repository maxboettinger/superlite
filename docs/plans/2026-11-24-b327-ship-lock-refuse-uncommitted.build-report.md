# superlite build report

projection: fixed forecast saved at lint 2026-11-24T16:36:46

                         Projected    Actual  Delta
wall-clock (min)               4.8       1.4  -3.4 (-71%)
agent cost (USD, +rework)      0.10      0.23  +0.13 (+121%)
task-minutes                   4.8       1.4  -3.4 (-71%)
agents                           1         3  +2 (+200%)
cost split: agents $0.23, rework $0.00, coordinator n/a, total $0.23
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.8 min)
model mix: sonnet 1 tasks $0.23
quality: tests 14233 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.8     1.4  -3.4 (-71%)     $0.231

takeaway: ran 71% faster than projected; cost 121% over; biggest miss T1
