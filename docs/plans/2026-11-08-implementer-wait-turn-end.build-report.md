# superlite build report

projection: fixed forecast saved at lint 2026-11-08T13:58:38

                         Projected    Actual  Delta
wall-clock (min)               1.0       0.6  -0.4 (-41%)
agent cost (USD, +rework)      0.01      0.35  +0.35 (+5162%)
task-minutes                   2.0       0.9  -1.1 (-55%)
agents                           2         4  +2 (+100%)
cost split: agents $0.35, rework $0.00, coordinator n/a, total $0.35
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.0 min)
model mix: sonnet 2 tasks $0.35
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.0     0.3  -0.7 (-69%)     $0.167
T1    sonnet      1.0     0.6  -0.4 (-41%)     $0.187

takeaway: ran 41% faster than projected; cost 5162% over; biggest miss T2
