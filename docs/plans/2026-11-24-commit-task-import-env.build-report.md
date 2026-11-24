# superlite build report

projection: fixed forecast saved at lint 2026-11-24T09:45:52 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.3       3.5  -5.8 (-62%)
agent cost (USD, +rework)      0.13      0.52  +0.39 (+307%)
task-minutes                   9.3       2.5  -6.9 (-74%)
agents                           1         3  +2 (+200%)
cost split: agents $0.52, rework $0.00, coordinator n/a, total $0.52
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 (9.3 min)
model mix: sonnet 2 tasks $0.52
quality: tests 13748 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.3     0.7  -8.6 (-92%)     $0.195
T2    sonnet      n/a     1.7  n/a             $0.327

takeaway: ran 62% faster than projected; cost 307% over; biggest miss T1
