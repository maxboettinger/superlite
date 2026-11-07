# superlite build report

projection: fixed forecast saved at lint 2026-11-07T15:26:47

                         Projected    Actual  Delta
wall-clock (min)               1.4       1.3  -0.1 (-7%)
agent cost (USD, +rework)      0.31      0.88  +0.57 (+182%)
task-minutes                   4.2       2.2  -2.0 (-48%)
agents                           3         4  +1 (+33%)
cost split: agents $0.88, rework $0.00, coordinator n/a, total $0.88
concurrency: peak 2 at once (projected 3); critical path actual T2; projected T1 (1.4 min)
model mix: sonnet 3 tasks $0.88
quality: tests 4022 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.4     0.7  -0.8 (-53%)     $0.244
T2    sonnet      1.3     0.7  -0.6 (-49%)     $0.244
T1    sonnet      1.4     0.8  -0.6 (-42%)     $0.390

takeaway: ran 7% faster than projected; cost 182% over; biggest miss T3
