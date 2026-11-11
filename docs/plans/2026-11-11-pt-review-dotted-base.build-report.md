# superlite build report

projection: fixed forecast saved at lint 2026-11-11T09:17:44

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.0  -0.6 (-36%)
agent cost (USD, +rework)      0.10      0.26  +0.15 (+147%)
task-minutes                   3.2       1.6  -1.6 (-49%)
agents                           2         4  +2 (+100%)
cost split: agents $0.26, rework $0.00, coordinator n/a, total $0.26
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 2 tasks $0.26
quality: tests 6104 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.6  -1.0 (-62%)     $0.099
T1    sonnet      1.6     1.0  -0.6 (-36%)     $0.157

takeaway: ran 36% faster than projected; cost 147% over; biggest miss T2
