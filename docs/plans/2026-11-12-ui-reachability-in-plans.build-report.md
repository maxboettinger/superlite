# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:39:17 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.4       1.1  -8.3 (-88%)
agent cost (USD, +rework)      0.21      0.34  +0.14 (+65%)
task-minutes                  18.6       1.7  -16.8 (-91%)
agents                           2         5  +3 (+150%)
cost split: agents $0.34, rework $0.00, coordinator n/a, total $0.34
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (9.4 min)
model mix: sonnet 2 tasks $0.34
quality: tests 7437 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.4     0.8  -8.6 (-92%)     $0.199
T2    sonnet      9.1     1.0  -8.2 (-90%)     $0.145

takeaway: ran 88% faster than projected; cost 65% over; biggest miss T1
