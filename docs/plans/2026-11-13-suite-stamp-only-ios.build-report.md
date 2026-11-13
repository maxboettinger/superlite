# superlite build report

projection: fixed forecast saved at lint 2026-11-13T06:02:53

                         Projected    Actual  Delta
wall-clock (min)               2.9       0.5  -2.5 (-84%)
agent cost (USD, +rework)      0.00      0.11  +0.11 (+2432%)
task-minutes                   2.9       0.5  -2.5 (-84%)
agents                           1         4  +3 (+300%)
cost split: agents $0.11, rework $0.00, coordinator n/a, total $0.11
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (2.9 min)
model mix: sonnet 1 tasks $0.11
quality: tests 9025 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.9     0.5  -2.5 (-84%)     $0.110

takeaway: ran 84% faster than projected; cost 2432% over; biggest miss T1
