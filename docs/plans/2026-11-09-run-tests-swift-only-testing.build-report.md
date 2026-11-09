# superlite build report

projection: fixed forecast saved at lint 2026-11-09T20:27:31

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.3  -0.3 (-19%)
agent cost (USD, +rework)      0.20      0.34  +0.14 (+69%)
task-minutes                   1.6       1.3  -0.3 (-19%)
agents                           1         3  +2 (+200%)
cost split: agents $0.34, rework $0.00, coordinator n/a, total $0.34
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 1 tasks $0.34
quality: tests 5065 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     1.3  -0.3 (-19%)     $0.343

takeaway: ran 19% faster than projected; cost 69% over; biggest miss T1
