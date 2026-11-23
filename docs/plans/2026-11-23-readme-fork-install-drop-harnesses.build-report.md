# superlite build report

projection: fixed forecast saved at lint 2026-11-23T08:33:53

                         Projected    Actual  Delta
wall-clock (min)               5.1       0.5  -4.6 (-90%)
agent cost (USD, +rework)      0.00      0.15  +0.14 (+3111%)
task-minutes                   5.1       0.5  -4.6 (-90%)
agents                           1         6  +5 (+500%)
cost split: agents $0.15, rework $0.00, coordinator n/a, total $0.15
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.1 min)
model mix: sonnet 1 tasks $0.15
quality: tests 13578 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.1     0.5  -4.6 (-90%)     $0.145

takeaway: ran 90% faster than projected; cost 3111% over; biggest miss T1
