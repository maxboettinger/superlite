# superlite build report

projection: fixed forecast saved at lint 2026-11-10T19:53:41 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.5      33.3  +29.8 (+847%)
agent cost (USD, +rework)      0.48      1.48  +1.00 (+207%)
task-minutes                   7.5       5.3  -2.1 (-29%)
agents                           5         8  +3 (+60%)
cost split: agents $1.19, rework $0.29, coordinator n/a, total $1.48
concurrency: peak 3 at once (projected 4); critical path actual T2; projected T3 > T4 (3.5 min)
model mix: sonnet 5 tasks $1.48
quality: tests 5654 passed, 0 failed; first-time pass n/a; rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.2     0.6  -0.6 (-54%)     $0.121
T4    sonnet      1.7     1.1  -0.6 (-35%)     $0.248
T1    sonnet      1.4     0.9  -0.5 (-33%)     $0.205
T2    sonnet      1.4     0.9  -0.4 (-32%)     $0.396
T3    sonnet      1.8     1.8  +0.0 (+1%)      $0.509

takeaway: ran 847% slower than projected; cost 207% over; biggest miss T5
