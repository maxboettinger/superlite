# superlite build report

projection: fixed forecast saved at lint 2026-11-10T11:47:41

                         Projected    Actual  Delta
wall-clock (min)               3.1       9.9  +6.8 (+217%)
agent cost (USD, +rework)      0.48      1.53  +1.05 (+219%)
task-minutes                   4.4       7.0  +2.7 (+62%)
agents                           3         7  +4 (+133%)
cost split: agents $1.09, rework $0.44, coordinator n/a, total $1.53
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T2 > T3 (3.1 min)
model mix: sonnet 3 tasks $1.53
quality: tests 5477 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.7     3.8  +2.1 (+123%)    $0.645
T1    sonnet      1.2     1.8  +0.6 (+49%)     $0.250
T3    sonnet      1.4     1.4  -0.0 (-1%)      $0.636

takeaway: ran 217% slower than projected; cost 219% over; biggest miss T2
