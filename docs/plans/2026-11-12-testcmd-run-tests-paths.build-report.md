# superlite build report

projection: fixed forecast saved at lint 2026-11-12T23:19:15 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              36.7      11.8  -24.9 (-68%)
agent cost (USD, +rework)      0.41      1.09  +0.68 (+167%)
task-minutes                  49.0       2.8  -46.2 (-94%)
agents                           4         7  +3 (+75%)
cost split: agents $0.68, rework $0.40, coordinator n/a, total $1.09
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T1 > T2 > T4 (36.7 min)
model mix: sonnet 4 tasks $1.09
quality: tests 8074 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     12.3     0.7  -11.7 (-95%)    $0.174
T4    sonnet     12.0     0.4  -11.6 (-97%)    $0.192  first-time miss
T2    sonnet     12.4     0.9  -11.5 (-93%)    $0.505  first-time miss
T3    sonnet     12.2     0.9  -11.4 (-93%)    $0.215

takeaway: ran 68% faster than projected; cost 167% over; biggest miss T1
