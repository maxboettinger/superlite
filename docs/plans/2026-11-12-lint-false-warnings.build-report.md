# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:25:00

                         Projected    Actual  Delta
wall-clock (min)               8.9      18.3  +9.4 (+105%)
agent cost (USD, +rework)      0.44      1.20  +0.75 (+169%)
task-minutes                  16.9       5.7  -11.2 (-66%)
agents                           4         6  +2 (+50%)
cost split: agents $1.07, rework $0.13, coordinator n/a, total $1.20
concurrency: peak 2 at once (projected 2); critical path actual T2 T4; projected T1 > T3 (8.9 min)
model mix: sonnet 4 tasks $1.20
quality: tests 7443 passed, 0 failed; first-time pass 3/4 (75%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      3.9     0.8  -3.1 (-80%)     $0.274  first-time miss
T3    sonnet      4.8     1.9  -3.0 (-61%)     $0.329
T2    sonnet      4.1     1.3  -2.8 (-69%)     $0.263
T1    sonnet      4.1     1.8  -2.3 (-56%)     $0.332

takeaway: ran 105% slower than projected; cost 169% over; biggest miss T4
