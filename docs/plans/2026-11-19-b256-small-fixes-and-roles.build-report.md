# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:53:18 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.6      10.3  +3.7 (+56%)
agent cost (USD, +rework)      0.21      0.45  +0.24 (+118%)
task-minutes                  23.7       3.4  -20.2 (-86%)
agents                           4         6  +2 (+50%)
cost split: agents $0.36, rework $0.09, coordinator n/a, total $0.45
concurrency: peak 3 at once (projected 4); critical path actual T3; projected T3 (6.6 min)
model mix: haiku 1 tasks $0.01, sonnet 3 tasks $0.44
quality: tests 12634 passed, 0 failed; first-time pass 3/4 (75%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    haiku       6.1     0.4  -5.7 (-94%)     $0.006
T3    sonnet      6.6     1.0  -5.6 (-85%)     $0.243  first-time miss
T2    sonnet      6.2     1.0  -5.2 (-83%)     $0.100
T4    sonnet      4.8     1.0  -3.7 (-78%)     $0.100

takeaway: ran 56% slower than projected; cost 118% over; biggest miss T1
