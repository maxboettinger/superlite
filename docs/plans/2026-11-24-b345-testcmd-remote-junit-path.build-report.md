# superlite build report

projection: fixed forecast saved at lint 2026-11-24T23:33:32

                         Projected    Actual  Delta
wall-clock (min)               5.4       9.7  +4.2 (+78%)
agent cost (USD, +rework)      0.17      0.37  +0.20 (+116%)
task-minutes                   5.4       1.0  -4.5 (-82%)
agents                           1         6  +5 (+500%)
cost split: agents $0.26, rework $0.12, coordinator n/a, total $0.37
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.4 min)
model mix: sonnet 1 tasks $0.37
quality: tests 14517 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.4     1.0  -4.5 (-82%)     $0.372  first-time miss

takeaway: ran 78% slower than projected; cost 116% over; biggest miss T1
