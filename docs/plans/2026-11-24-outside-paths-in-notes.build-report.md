# superlite build report

projection: fixed forecast saved at lint 2026-11-24T10:06:45 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.9      50.0  +40.1 (+404%)
agent cost (USD, +rework)      0.27      0.92  +0.64 (+238%)
task-minutes                  28.9       2.1  -26.7 (-93%)
agents                           3        12  +9 (+300%)
cost split: agents $0.48, rework $0.43, coordinator n/a, total $0.92
concurrency: peak 2 at once (projected 3); critical path actual T2; projected T2 (9.9 min)
model mix: sonnet 3 tasks $0.92
quality: tests 13731 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      9.8     0.6  -9.2 (-94%)     $0.135
T2    sonnet      9.9     1.0  -9.0 (-90%)     $0.547  first-time miss
T1    sonnet      9.2     0.6  -8.6 (-94%)     $0.233  first-time miss

takeaway: ran 404% slower than projected; cost 238% over; biggest miss T3
