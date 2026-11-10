# superlite build report

projection: fixed forecast saved at lint 2026-11-10T09:36:19 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.3       0.8  -0.4 (-33%)
agent cost (USD, +rework)      0.50      0.27  -0.23 (-45%)
task-minutes                   5.0       0.8  -4.2 (-83%)
agents                           4         3  -1 (-25%)
cost split: agents $0.27, rework $0.00, coordinator n/a, total $0.27
concurrency: peak 1 at once (projected 4); critical path actual T1; projected T1 (1.3 min)
model mix: sonnet 1 tasks $0.27
quality: tests 5302 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.3     0.8  -0.4 (-33%)     $0.274

takeaway: ran 33% faster than projected; cost 45% under; biggest miss T1
