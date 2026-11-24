# superlite build report

projection: fixed forecast saved at lint 2026-11-24T15:00:22

                         Projected    Actual  Delta
wall-clock (min)              15.9       2.2  -13.7 (-86%)
agent cost (USD, +rework)      0.22      0.67  +0.45 (+207%)
task-minutes                  24.2       2.9  -21.2 (-88%)
agents                           3         8  +5 (+167%)
cost split: agents $0.67, rework $0.00, coordinator n/a, total $0.67
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T3 (15.9 min)
model mix: sonnet 3 tasks $0.67
quality: tests 14094 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      8.3     0.9  -7.4 (-89%)     $0.214
T3    sonnet      7.6     0.3  -7.3 (-96%)     $0.052
T1    sonnet      8.3     1.8  -6.5 (-79%)     $0.402

takeaway: ran 86% faster than projected; cost 207% over; biggest miss T2
