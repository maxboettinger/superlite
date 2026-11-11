# superlite build report

projection: fixed forecast saved at lint 2026-11-11T01:10:47

                         Projected    Actual  Delta
wall-clock (min)               3.3       5.0  +1.7 (+50%)
agent cost (USD, +rework)      0.43      0.92  +0.49 (+115%)
task-minutes                   6.2       5.5  -0.7 (-11%)
agents                           4         6  +2 (+50%)
cost split: agents $0.92, rework $0.00, coordinator n/a, total $0.92
concurrency: peak 2 at once (projected 3); critical path actual T1 T2; projected T1 > T2 (3.3 min)
model mix: sonnet 4 tasks $0.92
quality: tests 4 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.8     2.8  +0.9 (+52%)     $0.425
T3    sonnet      1.5     0.8  -0.7 (-48%)     $0.152
T4    sonnet      1.4     0.8  -0.6 (-44%)     $0.152
T2    sonnet      1.5     1.2  -0.3 (-19%)     $0.190

takeaway: ran 50% slower than projected; cost 115% over; biggest miss T1
