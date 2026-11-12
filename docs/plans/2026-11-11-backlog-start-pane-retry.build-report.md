# superlite build report

projection: fixed forecast saved at lint 2026-11-11T23:55:38

                         Projected    Actual  Delta
wall-clock (min)               2.3      31.1  +28.8 (+1226%)
agent cost (USD, +rework)      0.22      0.40  +0.18 (+80%)
task-minutes                   3.9       1.4  -2.5 (-64%)
agents                           2         4  +2 (+100%)
cost split: agents $0.33, rework $0.07, coordinator n/a, total $0.40
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (2.3 min)
model mix: sonnet 2 tasks $0.40
quality: tests 6567 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.3     0.7  -1.6 (-70%)     $0.181
T2    sonnet      1.6     0.7  -0.9 (-55%)     $0.214  first-time miss

takeaway: ran 1226% slower than projected; cost 80% over; biggest miss T1
