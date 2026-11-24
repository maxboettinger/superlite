# superlite build report

projection: fixed forecast saved at lint 2026-11-24T12:47:05

                         Projected    Actual  Delta
wall-clock (min)               9.2       0.8  -8.4 (-92%)
agent cost (USD, +rework)      0.09      0.16  +0.07 (+79%)
task-minutes                   9.2       0.8  -8.4 (-92%)
agents                           1         4  +3 (+300%)
cost split: agents $0.16, rework $0.00, coordinator n/a, total $0.16
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.2 min)
model mix: sonnet 1 tasks $0.16
quality: tests 13954 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.2     0.8  -8.4 (-92%)     $0.159

takeaway: ran 92% faster than projected; cost 79% over; biggest miss T1
