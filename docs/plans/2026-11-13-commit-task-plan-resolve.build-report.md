# superlite build report

projection: fixed forecast saved at lint 2026-11-13T00:50:00 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.0       9.6  +2.6 (+37%)
agent cost (USD, +rework)      0.42      1.60  +1.18 (+278%)
task-minutes                  15.1       7.5  -7.6 (-50%)
agents                           4         8  +4 (+100%)
cost split: agents $1.50, rework $0.11, coordinator n/a, total $1.60
concurrency: peak 3 at once (projected 3); critical path actual T3; projected T2 > T4 (7.0 min)
model mix: sonnet 4 tasks $1.60
quality: tests 8339 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      2.9     0.3  -2.6 (-88%)     $0.073
T1    sonnet      4.0     1.7  -2.3 (-58%)     $0.361  first-time miss
T3    sonnet      4.1     2.7  -1.4 (-34%)     $0.661  first-time miss
T2    sonnet      4.1     2.8  -1.3 (-32%)     $0.506

takeaway: ran 37% slower than projected; cost 278% over; biggest miss T4
