# superlite build report

projection: fixed forecast saved at lint 2026-11-09T15:20:50

                         Projected    Actual  Delta
wall-clock (min)               2.3      31.2  +28.9 (+1266%)
agent cost (USD, +rework)      0.22      1.27  +1.05 (+468%)
task-minutes                   2.3       2.6  +0.3 (+13%)
agents                           2         8  +6 (+300%)
cost split: agents $0.73, rework $0.54, coordinator n/a, total $1.27
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (2.3 min)
model mix: sonnet 2 tasks $1.27
quality: tests 4812 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.1     1.7  +0.6 (+50%)     $0.365
T1    sonnet      1.1     0.9  -0.3 (-24%)     $0.908

takeaway: ran 1266% slower than projected; cost 468% over; biggest miss T2
