# superlite build report

projection: fixed forecast saved at lint 2026-11-07T09:57:36

                         Projected    Actual  Delta
wall-clock (min)               1.8       1.8  -0.0 (-0%)
agent cost (USD, +rework)      0.21      0.54  +0.33 (+155%)
task-minutes                   3.3       2.6  -0.7 (-22%)
agents                           2         4  +2 (+100%)
cost split: agents $0.54, rework $0.00, coordinator n/a, total $0.54
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (1.8 min)
model mix: sonnet 2 tasks $0.54
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.8     1.0  -0.8 (-44%)     $0.279
T1    sonnet      1.6     1.6  +0.1 (+4%)      $0.259

takeaway: ran on projection; cost 155% over; biggest miss T2
