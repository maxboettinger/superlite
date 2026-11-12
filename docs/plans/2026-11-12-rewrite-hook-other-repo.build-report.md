# superlite build report

projection: fixed forecast saved at lint 2026-11-12T04:02:26

                         Projected    Actual  Delta
wall-clock (min)               2.8       3.1  +0.3 (+11%)
agent cost (USD, +rework)      0.18      0.47  +0.29 (+162%)
task-minutes                   2.8       3.1  +0.3 (+11%)
agents                           1         3  +2 (+200%)
cost split: agents $0.47, rework $0.00, coordinator n/a, total $0.47
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (2.8 min)
model mix: sonnet 1 tasks $0.47
quality: tests 6795 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.8     3.1  +0.3 (+11%)     $0.468

takeaway: ran 11% slower than projected; cost 162% over; biggest miss T1
