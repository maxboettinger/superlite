# superlite build report

projection: fixed forecast saved at lint 2026-11-19T19:59:04 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.8      11.3  +3.5 (+44%)
agent cost (USD, +rework)      0.12      0.58  +0.46 (+401%)
task-minutes                   7.8       2.3  -5.6 (-71%)
agents                           1         6  +5 (+500%)
cost split: agents $0.47, rework $0.11, coordinator n/a, total $0.58
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (7.8 min)
model mix: sonnet 1 tasks $0.58
quality: tests 13146 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.8     2.3  -5.6 (-71%)     $0.579  first-time miss

takeaway: ran 44% slower than projected; cost 401% over; biggest miss T1
