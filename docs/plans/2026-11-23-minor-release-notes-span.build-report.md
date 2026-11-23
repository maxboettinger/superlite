# superlite build report

projection: fixed forecast saved at lint 2026-11-23T08:30:44

                         Projected    Actual  Delta
wall-clock (min)               3.2       0.6  -2.6 (-82%)
agent cost (USD, +rework)      0.00      0.15  +0.14 (+3388%)
task-minutes                   3.2       0.6  -2.6 (-82%)
agents                           1         3  +2 (+200%)
cost split: agents $0.15, rework $0.00, coordinator n/a, total $0.15
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.2 min)
model mix: sonnet 1 tasks $0.15
quality: tests 13564 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.2     0.6  -2.6 (-82%)     $0.148

takeaway: ran 82% faster than projected; cost 3388% over; biggest miss T1
