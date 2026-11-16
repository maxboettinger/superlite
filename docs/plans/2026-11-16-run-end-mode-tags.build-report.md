# superlite build report

projection: fixed forecast saved at lint 2026-11-16T15:28:53 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              13.1       1.3  -11.8 (-90%)
agent cost (USD, +rework)      0.16      0.29  +0.13 (+83%)
task-minutes                  13.1       0.9  -12.2 (-93%)
agents                           2         4  +2 (+100%)
cost split: agents $0.29, rework $0.00, coordinator n/a, total $0.29
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (13.1 min)
model mix: sonnet 2 tasks $0.29
quality: tests 11811 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.0     0.6  -6.4 (-92%)     $0.186
T2    sonnet      6.2     0.4  -5.8 (-94%)     $0.102

takeaway: ran 90% faster than projected; cost 83% over; biggest miss T1
