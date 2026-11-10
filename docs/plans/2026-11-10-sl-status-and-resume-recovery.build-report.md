# superlite build report

projection: fixed forecast saved at lint 2026-11-10T11:51:58

                         Projected    Actual  Delta
wall-clock (min)               3.7      10.9  +7.3 (+198%)
agent cost (USD, +rework)      0.77      1.57  +0.81 (+105%)
task-minutes                   5.3       4.3  -1.0 (-19%)
agents                           3         9  +6 (+200%)
cost split: agents $1.14, rework $0.44, coordinator n/a, total $1.57
concurrency: peak 3 at once (projected 2); critical path actual T1; projected T2 > T3 (3.7 min)
model mix: sonnet 3 tasks $1.57
quality: tests 5495 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.7     1.1  -0.6 (-33%)     $0.571
T3    sonnet      1.8     1.2  -0.5 (-30%)     $0.363
T2    sonnet      1.9     2.0  +0.1 (+5%)      $0.639

takeaway: ran 198% slower than projected; cost 105% over; biggest miss T1
