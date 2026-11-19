# superlite build report

projection: fixed forecast saved at lint 2026-11-19T18:31:39

                         Projected    Actual  Delta
wall-clock (min)               7.8       1.0  -6.8 (-87%)
agent cost (USD, +rework)      0.09      0.18  +0.08 (+90%)
task-minutes                   7.8       1.0  -6.8 (-87%)
agents                           1         4  +3 (+300%)
cost split: agents $0.18, rework $0.00, coordinator n/a, total $0.18
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (7.8 min)
model mix: sonnet 1 tasks $0.18
quality: tests 12936 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.8     1.0  -6.8 (-87%)     $0.176

takeaway: ran 87% faster than projected; cost 90% over; biggest miss T1
