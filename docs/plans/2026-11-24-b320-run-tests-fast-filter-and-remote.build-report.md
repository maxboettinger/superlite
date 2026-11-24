# superlite build report

projection: fixed forecast saved at lint 2026-11-24T15:03:29

                         Projected    Actual  Delta
wall-clock (min)              22.7      31.7  +9.0 (+40%)
agent cost (USD, +rework)      0.37      1.12  +0.75 (+200%)
task-minutes                  33.4      13.1  -20.3 (-61%)
agents                           3        10  +7 (+233%)
cost split: agents $0.92, rework $0.20, coordinator n/a, total $1.12
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T2 > T3 (22.7 min)
model mix: sonnet 3 tasks $1.12
quality: tests 14103 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     10.8     0.7  -10.1 (-94%)    $0.263  first-time miss
T1    sonnet     10.7     0.6  -10.1 (-94%)    $0.164
T3    sonnet     12.0    11.8  -0.2 (-1%)      $0.694  first-time miss

takeaway: ran 40% slower than projected; cost 200% over; biggest miss T2
