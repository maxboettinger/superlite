# superlite build report

projection: fixed forecast saved at lint 2026-11-12T22:48:08 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.4      11.5  +8.1 (+238%)
agent cost (USD, +rework)      0.49      0.96  +0.47 (+95%)
task-minutes                  13.0       2.9  -10.1 (-78%)
agents                           4        10  +6 (+150%)
cost split: agents $0.66, rework $0.30, coordinator n/a, total $0.96
concurrency: peak 4 at once (projected 4); critical path actual T2; projected T2 (3.4 min)
model mix: sonnet 4 tasks $0.96
quality: tests 8031 passed, 0 failed; first-time pass 1/4 (25%); rework dispatches 3; open incidents 6

task  model      pred  actual  delta             cost
T1    sonnet      3.3     0.6  -2.8 (-83%)     $0.224  first-time miss
T2    sonnet      3.4     0.8  -2.6 (-77%)     $0.293  first-time miss
T4    sonnet      3.0     0.6  -2.5 (-82%)     $0.203  first-time miss
T3    sonnet      3.2     1.0  -2.3 (-69%)     $0.238

takeaway: ran 238% slower than projected; cost 95% over; biggest miss T1
