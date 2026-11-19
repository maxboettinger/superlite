# superlite build report

projection: fixed forecast saved at lint 2026-11-19T17:01:53 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              22.7      26.4  +3.7 (+16%)
agent cost (USD, +rework)      0.30      1.21  +0.91 (+302%)
task-minutes                  22.7       4.9  -17.8 (-78%)
agents                           2        17  +15 (+750%)
cost split: agents $0.85, rework $0.35, coordinator n/a, total $1.21
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (22.7 min)
model mix: sonnet 2 tasks $1.21
quality: tests 12831 passed, 0 failed; first-time pass 0/2 (0%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     11.2     2.0  -9.2 (-82%)     $0.415  first-time miss
T1    sonnet     11.5     2.9  -8.6 (-75%)     $0.792  first-time miss

takeaway: ran 16% slower than projected; cost 302% over; biggest miss T2
