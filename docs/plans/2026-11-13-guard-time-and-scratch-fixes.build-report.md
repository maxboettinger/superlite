# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:35:36

                         Projected    Actual  Delta
wall-clock (min)               7.5      17.0  +9.5 (+127%)
agent cost (USD, +rework)      0.25      0.92  +0.66 (+261%)
task-minutes                  14.5       8.8  -5.8 (-40%)
agents                           2         7  +5 (+250%)
cost split: agents $0.74, rework $0.18, coordinator n/a, total $0.92
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (7.5 min)
model mix: sonnet 2 tasks $0.92
quality: tests 9382 passed, 0 failed; first-time pass 0/2 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.5     4.1  -3.4 (-45%)     $0.219  first-time miss
T2    sonnet      7.0     4.7  -2.4 (-34%)     $0.700  first-time miss

takeaway: ran 127% slower than projected; cost 261% over; biggest miss T1
