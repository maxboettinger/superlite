# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:36:42 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.1      14.6  +7.5 (+105%)
agent cost (USD, +rework)      0.49      1.45  +0.96 (+196%)
task-minutes                  26.2       5.5  -20.7 (-79%)
agents                           4        14  +10 (+250%)
cost split: agents $0.97, rework $0.48, coordinator n/a, total $1.45
concurrency: peak 3 at once (projected 4); critical path actual T1 T3; projected T1 (7.1 min)
model mix: sonnet 4 tasks $1.45
quality: tests 9395 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/4 (25%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      7.0     1.5  -5.5 (-78%)     $0.391  first-time miss
T2    sonnet      6.1     0.9  -5.1 (-85%)     $0.151
T1    sonnet      7.1     2.1  -5.1 (-71%)     $0.560  first-time miss
T4    sonnet      6.0     0.9  -5.0 (-84%)     $0.347  first-time miss

takeaway: ran 105% slower than projected; cost 196% over; biggest miss T3
