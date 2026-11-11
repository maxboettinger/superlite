# superlite build report

projection: fixed forecast saved at lint 2026-11-11T15:42:19

                         Projected    Actual  Delta
wall-clock (min)               4.7       3.8  -0.9 (-19%)
agent cost (USD, +rework)      0.34      0.62  +0.27 (+79%)
task-minutes                   4.7       3.1  -1.6 (-33%)
agents                           2         4  +2 (+100%)
cost split: agents $0.62, rework $0.00, coordinator n/a, total $0.62
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (4.7 min)
model mix: sonnet 2 tasks $0.62
quality: tests 6433 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      2.3     1.2  -1.1 (-47%)     $0.239
T1    sonnet      2.3     1.9  -0.5 (-20%)     $0.377

takeaway: ran 19% faster than projected; cost 79% over; biggest miss T2
