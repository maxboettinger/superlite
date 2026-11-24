# superlite build report

projection: fixed forecast saved at lint 2026-11-24T09:44:07

                         Projected    Actual  Delta
wall-clock (min)               7.7       1.7  -6.0 (-78%)
agent cost (USD, +rework)      0.17      0.37  +0.20 (+122%)
task-minutes                  15.5       2.1  -13.3 (-86%)
agents                           2         7  +5 (+250%)
cost split: agents $0.37, rework $0.00, coordinator n/a, total $0.37
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (7.7 min)
model mix: sonnet 2 tasks $0.37
quality: tests 13726 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      7.7     0.4  -7.3 (-94%)     $0.116
T1    sonnet      7.7     1.7  -6.0 (-78%)     $0.255  first-time miss

takeaway: ran 78% faster than projected; cost 122% over; biggest miss T2
