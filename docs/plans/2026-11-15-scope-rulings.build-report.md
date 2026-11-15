# superlite build report

projection: fixed forecast saved at lint 2026-11-15T11:45:37

                         Projected    Actual  Delta
wall-clock (min)               5.8      10.3  +4.5 (+76%)
agent cost (USD, +rework)      0.27      0.66  +0.39 (+143%)
task-minutes                  20.5       2.8  -17.7 (-86%)
agents                           4         7  +3 (+75%)
cost split: agents $0.53, rework $0.13, coordinator n/a, total $0.66
concurrency: peak 3 at once (projected 4); critical path actual T2; projected T4 (5.8 min)
model mix: sonnet 4 tasks $0.66
quality: tests 11101 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      5.8     0.4  -5.5 (-94%)     $0.106  first-time miss
T2    sonnet      5.6     0.9  -4.8 (-85%)     $0.345  first-time miss
T1    sonnet      4.6     0.8  -3.8 (-83%)     $0.103
T3    sonnet      4.4     0.8  -3.7 (-83%)     $0.103

takeaway: ran 76% slower than projected; cost 143% over; biggest miss T4
