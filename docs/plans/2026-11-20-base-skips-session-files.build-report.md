# superlite build report

projection: fixed forecast saved at lint 2026-11-20T09:10:50

                         Projected    Actual  Delta
wall-clock (min)               3.3      24.3  +21.0 (+636%)
agent cost (USD, +rework)      0.13      0.47  +0.34 (+270%)
task-minutes                   3.3       2.5  -0.8 (-24%)
agents                           1         5  +4 (+400%)
cost split: agents $0.21, rework $0.26, coordinator n/a, total $0.47
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.3 min)
model mix: sonnet 1 tasks $0.47
quality: tests 13241 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.3     2.5  -0.8 (-24%)     $0.469  first-time miss

takeaway: ran 636% slower than projected; cost 270% over; biggest miss T1
