# superlite build report

projection: fixed forecast saved at lint 2026-11-11T08:51:05

                         Projected    Actual  Delta
wall-clock (min)               2.2       1.2  -1.0 (-44%)
agent cost (USD, +rework)      0.15      0.23  +0.08 (+55%)
task-minutes                   2.2       1.2  -1.0 (-44%)
agents                           1         3  +2 (+200%)
cost split: agents $0.23, rework $0.00, coordinator n/a, total $0.23
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (2.2 min)
model mix: sonnet 1 tasks $0.23
quality: tests 6089 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.2     1.2  -1.0 (-44%)     $0.230

takeaway: ran 44% faster than projected; cost 55% over; biggest miss T1
