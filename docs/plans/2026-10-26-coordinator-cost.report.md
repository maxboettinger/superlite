# superlite build report

projection: fixed forecast saved at lint 2026-10-26T10:24:09

                         Projected    Actual  Delta
wall-clock (min)               5.8      10.2  +4.3 (+74%)
agent cost (USD, +rework)      0.38      1.66  +1.28 (+332%)
task-minutes                  15.3      14.1  -1.2 (-8%)
agents                           4        26  +22 (+550%)
cost split: agents $1.44, rework $0.22, coordinator $3.01, total $4.67
concurrency: peak 4 at once (projected 4); critical path actual T2; projected T2 (5.8 min)
model mix: sonnet 4 tasks $1.66, coordinator sonnet $3.01
quality: tests 676 passed, 2 failed; first-time pass n/a; rework dispatches 2; open incidents 18

task  model      pred  actual  delta             cost
T2    sonnet      5.8     4.8  -1.1 (-18%)     $0.734
T4    sonnet      3.2     3.0  -0.2 (-6%)      $0.301
T3    sonnet      3.1     3.3  +0.2 (+7%)      $0.303
T1    sonnet      3.2     3.0  -0.2 (-5%)      $0.323

takeaway: ran 74% slower than projected; cost 332% over; biggest miss T2
