# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:27:48

                         Projected    Actual  Delta
wall-clock (min)               6.3      17.7  +11.4 (+180%)
agent cost (USD, +rework)      0.29      0.71  +0.42 (+143%)
task-minutes                  16.5       2.2  -14.3 (-87%)
agents                           3         8  +5 (+167%)
cost split: agents $0.50, rework $0.21, coordinator n/a, total $0.71
concurrency: peak 3 at once (projected 3); critical path actual T2; projected T1 (6.3 min)
model mix: sonnet 3 tasks $0.71
quality: tests 7422 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.3     0.9  -5.4 (-86%)     $0.183
T2    sonnet      5.7     0.7  -5.0 (-88%)     $0.283  first-time miss
T3    sonnet      4.5     0.7  -3.8 (-85%)     $0.245  first-time miss

takeaway: ran 180% slower than projected; cost 143% over; biggest miss T1
