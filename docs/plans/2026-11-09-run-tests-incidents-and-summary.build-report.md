# superlite build report

projection: fixed forecast saved at lint 2026-11-09T17:33:03

                         Projected    Actual  Delta
wall-clock (min)               3.9       4.2  +0.3 (+7%)
agent cost (USD, +rework)      0.40      0.89  +0.49 (+122%)
task-minutes                   3.9       3.4  -0.5 (-14%)
agents                           3         7  +4 (+133%)
cost split: agents $0.89, rework $0.00, coordinator n/a, total $0.89
concurrency: peak 1 at once (projected 1); critical path actual T1 T2 T3; projected T1 > T2 > T3 (3.9 min)
model mix: sonnet 3 tasks $0.89
quality: tests 4914 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.5     0.9  -0.6 (-42%)     $0.165
T1    sonnet      1.2     1.2  +0.0 (+4%)      $0.387
T3    sonnet      1.2     1.3  +0.0 (+4%)      $0.335

takeaway: ran 7% slower than projected; cost 122% over; biggest miss T2
