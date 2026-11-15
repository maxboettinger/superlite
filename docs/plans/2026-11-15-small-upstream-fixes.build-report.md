# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:14:50

                         Projected    Actual  Delta
wall-clock (min)               3.5       9.4  +6.0 (+172%)
agent cost (USD, +rework)      0.01      0.36  +0.35 (+3203%)
task-minutes                   9.8       1.7  -8.2 (-83%)
agents                           3         5  +2 (+67%)
cost split: agents $0.27, rework $0.09, coordinator n/a, total $0.36
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T3 (3.5 min)
model mix: sonnet 3 tasks $0.36
quality: tests 10103 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.4     0.4  -3.1 (-89%)     $0.083
T2    sonnet      2.9     0.4  -2.6 (-87%)     $0.083
T3    sonnet      3.5     0.9  -2.6 (-74%)     $0.192  first-time miss

takeaway: ran 172% slower than projected; cost 3203% over; biggest miss T1
