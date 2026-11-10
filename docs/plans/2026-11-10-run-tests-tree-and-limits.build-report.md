# superlite build report

projection: fixed forecast saved at lint 2026-11-10T20:58:55

                         Projected    Actual  Delta
wall-clock (min)               3.8       4.0  +0.2 (+5%)
agent cost (USD, +rework)      0.58      0.91  +0.33 (+57%)
task-minutes                   6.6       6.3  -0.3 (-4%)
agents                           4         5  +1 (+25%)
cost split: agents $0.91, rework $0.00, coordinator n/a, total $0.91
concurrency: peak 2 at once (projected 3); critical path actual T3 T4; projected T3 > T4 (3.8 min)
model mix: sonnet 4 tasks $0.91
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      1.9     1.3  -0.5 (-28%)     $0.314
T1    sonnet      1.4     1.5  +0.1 (+10%)     $0.134
T2    sonnet      1.4     1.5  +0.1 (+5%)      $0.134
T3    sonnet      1.9     1.9  +0.0 (+2%)      $0.325

takeaway: ran 5% slower than projected; cost 57% over; biggest miss T4
