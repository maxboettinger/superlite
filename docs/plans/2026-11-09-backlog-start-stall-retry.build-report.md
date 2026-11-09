# superlite build report

projection: fixed forecast saved at lint 2026-11-09T10:21:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.4       1.3  -0.1 (-8%)
agent cost (USD, +rework)      0.18      0.58  +0.41 (+231%)
task-minutes                   2.5       1.8  -0.6 (-26%)
agents                           2         4  +2 (+100%)
cost split: agents $0.58, rework $0.00, coordinator n/a, total $0.58
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.4 min)
model mix: sonnet 2 tasks $0.58
quality: tests 4568 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.4     0.7  -0.7 (-47%)     $0.323
T1    sonnet      1.1     1.1  +0.0 (+2%)      $0.259

takeaway: ran 8% faster than projected; cost 231% over; biggest miss T2
