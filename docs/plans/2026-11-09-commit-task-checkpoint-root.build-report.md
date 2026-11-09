# superlite build report

projection: fixed forecast saved at lint 2026-11-09T17:58:08

                         Projected    Actual  Delta
wall-clock (min)               2.3      12.7  +10.4 (+454%)
agent cost (USD, +rework)      0.23      0.71  +0.48 (+204%)
task-minutes                   2.3       2.4  +0.1 (+4%)
agents                           2         4  +2 (+100%)
cost split: agents $0.55, rework $0.16, coordinator n/a, total $0.71
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (2.3 min)
model mix: sonnet 2 tasks $0.71
quality: tests 4935 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.2     1.3  +0.2 (+14%)     $0.258
T1    sonnet      1.1     1.1  -0.1 (-7%)      $0.451

takeaway: ran 454% slower than projected; cost 204% over; biggest miss T2
