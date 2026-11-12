# superlite build report

projection: fixed forecast saved at lint 2026-11-12T11:24:09 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.4      63.1  +57.7 (+1064%)
agent cost (USD, +rework)      0.48      1.19  +0.71 (+146%)
task-minutes                   8.8       5.3  -3.5 (-39%)
agents                           4         8  +4 (+100%)
cost split: agents $1.01, rework $0.18, coordinator n/a, total $1.19
concurrency: peak 2 at once (projected 3); critical path actual T3 T4; projected T3 > T4 (5.4 min)
model mix: sonnet 4 tasks $1.19
quality: tests 7220 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      2.7     1.7  -1.0 (-38%)     $0.378  first-time miss
T1    sonnet      1.8     0.8  -0.9 (-53%)     $0.133
T2    sonnet      1.6     0.8  -0.8 (-48%)     $0.133
T4    sonnet      2.8     2.0  -0.7 (-27%)     $0.547  first-time miss

takeaway: ran 1064% slower than projected; cost 146% over; biggest miss T3
