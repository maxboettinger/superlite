# superlite build report

projection: fixed forecast saved at lint 2026-11-09T10:27:00 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.9      33.9  +30.0 (+765%)
agent cost (USD, +rework)      0.37      1.93  +1.56 (+421%)
task-minutes                   3.9       6.0  +2.0 (+52%)
agents                           3         7  +4 (+133%)
cost split: agents $1.65, rework $0.27, coordinator n/a, total $1.93
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 > T3 (3.9 min)
model mix: sonnet 4 tasks $1.93
quality: tests 4590 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.2     2.3  +1.1 (+85%)     $0.522
T1    sonnet      1.1     0.6  -0.5 (-49%)     $0.547
T3    sonnet      1.6     1.4  -0.1 (-8%)      $0.465
T4    sonnet      n/a     1.7  n/a             $0.392

takeaway: ran 765% slower than projected; cost 421% over; biggest miss T2
