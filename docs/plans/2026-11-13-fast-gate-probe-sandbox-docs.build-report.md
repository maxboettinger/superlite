# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:53:31

                         Projected    Actual  Delta
wall-clock (min)               7.4       2.1  -5.3 (-72%)
agent cost (USD, +rework)      0.00      0.23  +0.23 (+6521%)
task-minutes                   7.4       2.1  -5.3 (-72%)
agents                           1         3  +2 (+200%)
cost split: agents $0.23, rework $0.00, coordinator n/a, total $0.23
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (7.4 min)
model mix: sonnet 1 tasks $0.23
quality: tests 9365 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.4     2.1  -5.3 (-72%)     $0.230

takeaway: ran 72% faster than projected; cost 6521% over; biggest miss T1
