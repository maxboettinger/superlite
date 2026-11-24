# superlite build report

projection: fixed forecast saved at lint 2026-11-24T17:08:00

                         Projected    Actual  Delta
wall-clock (min)               7.1      12.5  +5.5 (+77%)
agent cost (USD, +rework)      0.48      1.01  +0.54 (+112%)
task-minutes                  14.2      19.2  +5.1 (+36%)
agents                           4        10  +6 (+150%)
cost split: agents $1.01, rework $0.00, coordinator n/a, total $1.01
concurrency: peak 3 at once (projected 3); critical path actual T1 T2; projected T1 > T3 (7.1 min)
model mix: sonnet 4 tasks $1.01
quality: tests 14275 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.3    11.4  +8.1 (+245%)    $0.404
T4    sonnet      3.8     0.7  -3.2 (-83%)     $0.173
T3    sonnet      3.8     6.6  +2.8 (+72%)     $0.270
T1    sonnet      3.2     0.6  -2.6 (-80%)     $0.166

takeaway: ran 77% slower than projected; cost 112% over; biggest miss T2
