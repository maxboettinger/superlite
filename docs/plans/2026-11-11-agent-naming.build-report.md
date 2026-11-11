# superlite build report

projection: fixed forecast saved at lint 2026-11-11T11:54:30 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.3      20.1  +17.9 (+782%)
agent cost (USD, +rework)      0.42      1.14  +0.73 (+174%)
task-minutes                   7.1      24.1  +17.0 (+241%)
agents                           4         5  +1 (+25%)
cost split: agents $1.14, rework $0.00, coordinator n/a, total $1.14
concurrency: peak 3 at once (projected 4); critical path actual T1; projected T2 (2.3 min)
model mix: sonnet 3 tasks $1.14
quality: tests 6249 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6    20.1  +18.6 (+1163%)  $0.527
T4    sonnet      1.6     3.1  +1.5 (+92%)     $0.441
T3    sonnet      1.6     0.9  -0.7 (-44%)     $0.174

takeaway: ran 782% slower than projected; cost 174% over; biggest miss T1
