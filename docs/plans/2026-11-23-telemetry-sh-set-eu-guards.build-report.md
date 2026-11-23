# superlite build report

projection: fixed forecast saved at lint 2026-11-23T08:12:07 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.7       0.6  -3.1 (-84%)
agent cost (USD, +rework)      0.10      0.16  +0.06 (+57%)
task-minutes                   3.7       0.6  -3.1 (-84%)
agents                           1         3  +2 (+200%)
cost split: agents $0.16, rework $0.00, coordinator n/a, total $0.16
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.7 min)
model mix: sonnet 1 tasks $0.16
quality: tests 13563 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.7     0.6  -3.1 (-84%)     $0.161

takeaway: ran 84% faster than projected; cost 57% over; biggest miss T1
