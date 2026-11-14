# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:46:38

                         Projected    Actual  Delta
wall-clock (min)               3.4       6.5  +3.2 (+94%)
agent cost (USD, +rework)      0.14      0.28  +0.14 (+101%)
task-minutes                   3.4       0.7  -2.7 (-79%)
agents                           1         6  +5 (+500%)
cost split: agents $0.20, rework $0.08, coordinator n/a, total $0.28
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.4 min)
model mix: sonnet 1 tasks $0.28
quality: tests 9974 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.4     0.7  -2.7 (-79%)     $0.283  first-time miss

takeaway: ran 94% slower than projected; cost 101% over; biggest miss T1
