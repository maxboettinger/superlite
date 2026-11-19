# superlite build report

projection: fixed forecast saved at lint 2026-11-19T17:57:11 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.2      30.1  +13.9 (+86%)
agent cost (USD, +rework)      0.27      1.05  +0.78 (+289%)
task-minutes                  16.2       7.5  -8.7 (-54%)
agents                           2        16  +14 (+700%)
cost split: agents $0.56, rework $0.49, coordinator n/a, total $1.05
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (16.2 min)
model mix: sonnet 2 tasks $1.05
quality: tests 12996 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.9     2.0  -5.9 (-74%)     $0.889  first-time miss
T2    sonnet      8.3     5.5  -2.8 (-34%)     $0.160

takeaway: ran 86% slower than projected; cost 289% over; biggest miss T1
