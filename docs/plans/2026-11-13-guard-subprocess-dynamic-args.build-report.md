# superlite build report

projection: fixed forecast saved at lint 2026-11-13T06:40:28 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.0       8.8  +0.8 (+11%)
agent cost (USD, +rework)      0.30      0.49  +0.19 (+64%)
task-minutes                   8.0       2.7  -5.3 (-66%)
agents                           2         5  +3 (+150%)
cost split: agents $0.41, rework $0.09, coordinator n/a, total $0.49
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (8.0 min)
model mix: sonnet 2 tasks $0.49
quality: tests 9086 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.1     1.0  -3.1 (-75%)     $0.223
T2    sonnet      3.9     1.7  -2.2 (-56%)     $0.268  first-time miss

takeaway: ran 11% slower than projected; cost 64% over; biggest miss T1
