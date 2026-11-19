# superlite build report

projection: fixed forecast saved at lint 2026-11-19T20:03:03 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.4       5.4  -4.0 (-43%)
agent cost (USD, +rework)      0.15      0.37  +0.22 (+145%)
task-minutes                   9.4       1.3  -8.1 (-86%)
agents                           1         6  +5 (+500%)
cost split: agents $0.24, rework $0.14, coordinator n/a, total $0.37
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.4 min)
model mix: sonnet 1 tasks $0.37
quality: tests 13150 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.4     1.3  -8.1 (-86%)     $0.375  first-time miss

takeaway: ran 43% faster than projected; cost 145% over; biggest miss T1
