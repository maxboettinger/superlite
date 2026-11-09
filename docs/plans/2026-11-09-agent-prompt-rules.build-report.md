# superlite build report

projection: fixed forecast saved at lint 2026-11-09T18:15:37

                         Projected    Actual  Delta
wall-clock (min)               1.3       0.7  -0.6 (-45%)
agent cost (USD, +rework)      0.01      0.44  +0.43 (+3527%)
task-minutes                   3.5       1.2  -2.4 (-67%)
agents                           3         4  +1 (+33%)
cost split: agents $0.44, rework $0.00, coordinator n/a, total $0.44
concurrency: peak 2 at once (projected 3); critical path actual T1; projected T1 (1.3 min)
model mix: sonnet 3 tasks $0.44
quality: tests 4962 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.3     0.3  -1.0 (-75%)     $0.117
T1    sonnet      1.3     0.5  -0.7 (-59%)     $0.207
T3    sonnet      1.0     0.3  -0.7 (-68%)     $0.117

takeaway: ran 45% faster than projected; cost 3527% over; biggest miss T2
