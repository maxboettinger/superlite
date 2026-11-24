# superlite build report

projection: fixed forecast saved at lint 2026-11-24T13:13:45

                         Projected    Actual  Delta
wall-clock (min)              19.2      14.5  -4.6 (-24%)
agent cost (USD, +rework)      0.33      0.70  +0.37 (+113%)
task-minutes                  25.9       4.5  -21.5 (-83%)
agents                           4        13  +9 (+225%)
cost split: agents $0.61, rework $0.09, coordinator n/a, total $0.70
concurrency: peak 2 at once (projected 2); critical path actual T1 T3 T4; projected T1 > T3 > T4 (19.2 min)
model mix: sonnet 4 tasks $0.70
quality: tests 13978 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.8     0.7  -6.1 (-89%)     $0.214
T2    sonnet      6.8     0.8  -6.0 (-88%)     $0.209  first-time miss
T4    sonnet      6.1     0.4  -5.7 (-94%)     $0.161  first-time miss
T3    sonnet      6.2     2.5  -3.7 (-60%)     $0.117

takeaway: ran 24% faster than projected; cost 113% over; biggest miss T1
