# superlite build report

projection: fixed forecast saved at lint 2026-11-13T12:35:28

                         Projected    Actual  Delta
wall-clock (min)               4.6       3.2  -1.4 (-31%)
agent cost (USD, +rework)      0.32      1.13  +0.82 (+255%)
task-minutes                  11.5       5.2  -6.2 (-54%)
agents                           3         7  +4 (+133%)
cost split: agents $1.13, rework $0.00, coordinator n/a, total $1.13
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T1 (4.6 min)
model mix: sonnet 3 tasks $1.13
quality: tests 9714 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 2/3 (66%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.9     0.9  -2.9 (-76%)     $0.240  first-time miss
T3    sonnet      3.0     1.1  -1.9 (-64%)     $0.293
T1    sonnet      4.6     3.2  -1.4 (-31%)     $0.602

takeaway: ran 31% faster than projected; cost 255% over; biggest miss T2
