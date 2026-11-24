# superlite build report

projection: fixed forecast saved at lint 2026-11-24T08:08:20

                         Projected    Actual  Delta
wall-clock (min)               3.7       0.9  -2.7 (-74%)
agent cost (USD, +rework)      0.00      0.12  +0.12 (+3909%)
task-minutes                   3.7       0.9  -2.7 (-74%)
agents                           1         3  +2 (+200%)
cost split: agents $0.12, rework $0.00, coordinator n/a, total $0.12
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.7 min)
model mix: sonnet 1 tasks $0.12
quality: tests 13678 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.7     0.9  -2.7 (-74%)     $0.118  first-time miss

takeaway: ran 74% faster than projected; cost 3909% over; biggest miss T1
