# superlite build report

projection: fixed forecast saved at lint 2026-11-13T05:08:01

                         Projected    Actual  Delta
wall-clock (min)               4.1      34.0  +29.9 (+727%)
agent cost (USD, +rework)      0.44      1.79  +1.35 (+306%)
task-minutes                  17.0       3.9  -13.2 (-77%)
agents                           5        15  +10 (+200%)
cost split: agents $0.99, rework $0.80, coordinator n/a, total $1.79
concurrency: peak 4 at once (projected 5); critical path actual T3; projected T3 (4.1 min)
model mix: sonnet 5 tasks $1.79
quality: tests 8972 passed, 0 failed; first-time pass 2/5 (40%); rework dispatches 6; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      3.8     0.6  -3.2 (-85%)     $0.150
T3    sonnet      4.1     1.4  -2.7 (-66%)     $0.900  first-time miss
T2    sonnet      3.2     0.7  -2.6 (-80%)     $0.290  first-time miss
T1    sonnet      2.9     0.6  -2.4 (-80%)     $0.150
T5    sonnet      3.0     0.7  -2.3 (-78%)     $0.304  first-time miss

takeaway: ran 727% slower than projected; cost 306% over; biggest miss T4
