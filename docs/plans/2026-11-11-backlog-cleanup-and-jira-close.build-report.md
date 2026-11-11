# superlite build report

projection: fixed forecast saved at lint 2026-11-11T13:49:14

                         Projected    Actual  Delta
wall-clock (min)               3.3      17.7  +14.4 (+440%)
agent cost (USD, +rework)      0.45      1.10  +0.64 (+142%)
task-minutes                   6.5       5.8  -0.7 (-11%)
agents                           4         7  +3 (+75%)
cost split: agents $0.89, rework $0.21, coordinator n/a, total $1.10
concurrency: peak 3 at once (projected 3); critical path actual T1 T2; projected T1 > T2 (3.3 min)
model mix: sonnet 4 tasks $1.10
quality: tests 6338 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.6     1.3  -0.4 (-22%)     $0.178
T4    sonnet      1.6     1.3  -0.3 (-21%)     $0.178
T2    sonnet      1.6     1.4  -0.3 (-16%)     $0.396
T1    sonnet      1.6     1.9  +0.2 (+14%)     $0.343

takeaway: ran 440% slower than projected; cost 142% over; biggest miss T3
