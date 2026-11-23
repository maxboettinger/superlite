# superlite build report

projection: fixed forecast saved at lint 2026-11-23T07:55:16

                         Projected    Actual  Delta
wall-clock (min)               3.1       0.3  -2.8 (-90%)
agent cost (USD, +rework)      0.00      0.10  +0.10 (+3567%)
task-minutes                   3.1       0.3  -2.8 (-90%)
agents                           1         3  +2 (+200%)
cost split: agents $0.10, rework $0.00, coordinator n/a, total $0.10
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.1 min)
model mix: sonnet 1 tasks $0.10
quality: tests 13555 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.1     0.3  -2.8 (-90%)     $0.104

takeaway: ran 90% faster than projected; cost 3567% over; biggest miss T1
