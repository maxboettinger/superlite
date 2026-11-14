# superlite build report

projection: fixed forecast saved at lint 2026-11-14T12:31:05 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.5      12.6  +5.1 (+68%)
agent cost (USD, +rework)      0.00      0.12  +0.12 (+2436%)
task-minutes                   7.5       0.2  -7.3 (-97%)
agents                           1         4  +3 (+300%)
cost split: agents $0.06, rework $0.06, coordinator n/a, total $0.12
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (7.5 min)
model mix: sonnet 1 tasks $0.12
quality: tests 9724 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.5     0.2  -7.3 (-97%)     $0.122  first-time miss

takeaway: ran 68% slower than projected; cost 2436% over; biggest miss T1
