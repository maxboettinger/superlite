# superlite build report

projection: fixed forecast saved at lint 2026-11-12T05:24:48

                         Projected    Actual  Delta
wall-clock (min)               4.6       2.3  -2.3 (-50%)
agent cost (USD, +rework)      0.52      0.74  +0.22 (+43%)
task-minutes                   9.2       3.0  -6.2 (-68%)
agents                           4         7  +3 (+75%)
cost split: agents $0.74, rework $0.00, coordinator n/a, total $0.74
concurrency: peak 2 at once (projected 3); critical path actual T2 T3; projected T2 > T3 (4.6 min)
model mix: sonnet 4 tasks $0.74
quality: tests 6893 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.0     0.7  -2.3 (-76%)     $0.180
T2    sonnet      3.1     1.3  -1.8 (-59%)     $0.317
T3    sonnet      1.5     0.3  -1.3 (-83%)     $0.062
T4    sonnet      1.5     0.7  -0.8 (-51%)     $0.180

takeaway: ran 50% faster than projected; cost 43% over; biggest miss T1
