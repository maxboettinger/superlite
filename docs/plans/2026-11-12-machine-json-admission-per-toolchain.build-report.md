# superlite build report

projection: fixed forecast saved at lint 2026-11-12T19:05:16 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.4       8.6  +5.2 (+155%)
agent cost (USD, +rework)      0.43      0.71  +0.28 (+65%)
task-minutes                  13.0       3.2  -9.8 (-75%)
agents                           4         8  +4 (+100%)
cost split: agents $0.57, rework $0.13, coordinator n/a, total $0.71
concurrency: peak 2 at once (projected 4); critical path actual T4; projected T1 (3.4 min)
model mix: sonnet 4 tasks $0.71
quality: tests 7985 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      3.2     0.5  -2.7 (-84%)     $0.113
T4    sonnet      3.1     0.5  -2.6 (-84%)     $0.244  first-time miss
T1    sonnet      3.4     0.9  -2.5 (-74%)     $0.169
T2    sonnet      3.3     1.3  -2.0 (-60%)     $0.180  first-time miss

takeaway: ran 155% slower than projected; cost 65% over; biggest miss T3
