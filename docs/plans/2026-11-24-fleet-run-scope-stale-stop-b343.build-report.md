# superlite build report

projection: fixed forecast saved at lint 2026-11-24T22:37:12 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.6      16.5  +5.9 (+56%)
agent cost (USD, +rework)      0.23      0.72  +0.49 (+214%)
task-minutes                  10.6       3.0  -7.5 (-71%)
agents                           2         6  +4 (+200%)
cost split: agents $0.59, rework $0.13, coordinator n/a, total $0.72
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (10.6 min)
model mix: sonnet 2 tasks $0.72
quality: tests 14500 passed, 0 failed; first-time pass 0/2 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.2     1.3  -3.9 (-75%)     $0.268  first-time miss
T2    sonnet      5.4     1.7  -3.6 (-68%)     $0.453  first-time miss

takeaway: ran 56% slower than projected; cost 214% over; biggest miss T1
