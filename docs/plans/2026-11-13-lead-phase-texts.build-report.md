# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:16:44 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.3       0.8  -4.5 (-85%)
agent cost (USD, +rework)      0.11      0.31  +0.19 (+169%)
task-minutes                   9.7       1.3  -8.4 (-87%)
agents                           2         3  +1 (+50%)
cost split: agents $0.31, rework $0.00, coordinator n/a, total $0.31
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (5.3 min)
model mix: sonnet 2 tasks $0.31
quality: tests 9274 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.3     0.7  -4.6 (-87%)     $0.188
T2    sonnet      4.4     0.6  -3.8 (-87%)     $0.117

takeaway: ran 85% faster than projected; cost 169% over; biggest miss T1
