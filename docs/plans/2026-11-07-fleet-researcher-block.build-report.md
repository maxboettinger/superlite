# superlite build report

projection: fixed forecast saved at lint 2026-11-07T23:52:05

                         Projected    Actual  Delta
wall-clock (min)               1.2       0.5  -0.7 (-56%)
agent cost (USD, +rework)      0.10      0.23  +0.13 (+137%)
task-minutes                   1.2       0.5  -0.7 (-56%)
agents                           1         3  +2 (+200%)
cost split: agents $0.23, rework $0.00, coordinator n/a, total $0.23
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.2 min)
model mix: sonnet 1 tasks $0.23
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.2     0.5  -0.7 (-56%)     $0.228

takeaway: ran 56% faster than projected; cost 137% over; biggest miss T1
