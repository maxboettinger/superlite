# superlite build report

projection: fixed forecast saved at lint 2026-11-24T18:52:47

                         Projected    Actual  Delta
wall-clock (min)               8.5       3.3  -5.2 (-61%)
agent cost (USD, +rework)      0.19      0.57  +0.38 (+198%)
task-minutes                   8.5       3.3  -5.2 (-61%)
agents                           1         3  +2 (+200%)
cost split: agents $0.57, rework $0.00, coordinator n/a, total $0.57
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (8.5 min)
model mix: sonnet 1 tasks $0.57
quality: tests 14383 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      8.5     3.3  -5.2 (-61%)     $0.567

takeaway: ran 61% faster than projected; cost 198% over; biggest miss T1
