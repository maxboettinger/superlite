# superlite build report

projection: fixed forecast saved at lint 2026-11-12T09:09:29

                         Projected    Actual  Delta
wall-clock (min)               2.5      28.3  +25.8 (+1015%)
agent cost (USD, +rework)      0.14      0.55  +0.41 (+288%)
task-minutes                   5.5       4.9  -0.6 (-11%)
agents                           3         6  +3 (+100%)
cost split: agents $0.45, rework $0.10, coordinator n/a, total $0.55
concurrency: peak 2 at once (projected 3); critical path actual T2; projected T2 (2.5 min)
model mix: sonnet 3 tasks $0.55
quality: tests 7042 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      2.5     1.8  -0.7 (-28%)     $0.353  first-time miss
T3    sonnet      1.5     1.5  +0.0 (+3%)      $0.100
T1    sonnet      1.5     1.5  +0.0 (+2%)      $0.100

takeaway: ran 1015% slower than projected; cost 288% over; biggest miss T2
