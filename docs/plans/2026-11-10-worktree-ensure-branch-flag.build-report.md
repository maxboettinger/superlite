# superlite build report

projection: fixed forecast saved at lint 2026-11-10T12:49:36

                         Projected    Actual  Delta
wall-clock (min)               1.3       1.3  -0.0 (-3%)
agent cost (USD, +rework)      0.12      0.21  +0.08 (+66%)
task-minutes                   1.3       1.3  -0.0 (-3%)
agents                           1         3  +2 (+200%)
cost split: agents $0.21, rework $0.00, coordinator n/a, total $0.21
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.3 min)
model mix: sonnet 1 tasks $0.21
quality: tests 5567 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.3     1.3  -0.0 (-3%)      $0.206

takeaway: ran 3% faster than projected; cost 66% over; biggest miss T1
