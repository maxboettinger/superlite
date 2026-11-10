# superlite build report

projection: fixed forecast saved at lint 2026-11-10T10:41:38 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.0      15.4  +12.4 (+415%)
agent cost (USD, +rework)      0.62      1.83  +1.21 (+194%)
task-minutes                   5.8       5.2  -0.6 (-10%)
agents                           4         7  +3 (+75%)
cost split: agents $1.65, rework $0.18, coordinator n/a, total $1.83
concurrency: peak 3 at once (projected 3); critical path actual T4; projected T1 > T2 (3.0 min)
model mix: sonnet 4 tasks $1.83
quality: tests 5380 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     1.2  -0.4 (-24%)     $0.397
T3    sonnet      1.4     1.1  -0.4 (-26%)     $0.400
T2    sonnet      1.4     1.5  +0.1 (+8%)      $0.479
T4    sonnet      1.3     1.4  +0.0 (+4%)      $0.553

takeaway: ran 415% slower than projected; cost 194% over; biggest miss T1
