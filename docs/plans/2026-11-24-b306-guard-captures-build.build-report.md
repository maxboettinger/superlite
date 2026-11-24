# superlite build report

projection: fixed forecast saved at lint 2026-11-24T09:49:24 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              25.2       2.8  -22.4 (-89%)
agent cost (USD, +rework)      0.38      0.68  +0.29 (+76%)
task-minutes                  38.1       3.5  -34.6 (-91%)
agents                           3        10  +7 (+233%)
cost split: agents $0.68, rework $0.00, coordinator n/a, total $0.68
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T2 > T1 (25.2 min)
model mix: sonnet 3 tasks $0.68
quality: tests 13726 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     12.9     1.3  -11.6 (-90%)    $0.230
T3    sonnet     12.9     1.3  -11.5 (-90%)    $0.270
T2    sonnet     12.3     0.9  -11.5 (-93%)    $0.176

takeaway: ran 89% faster than projected; cost 76% over; biggest miss T1
