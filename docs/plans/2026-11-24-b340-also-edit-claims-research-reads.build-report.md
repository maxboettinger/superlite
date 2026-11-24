# superlite build report

projection: fixed forecast saved at lint 2026-11-24T21:36:37

                         Projected    Actual  Delta
wall-clock (min)              10.7       6.2  -4.6 (-42%)
agent cost (USD, +rework)      0.39      1.23  +0.85 (+219%)
task-minutes                  15.9       2.7  -13.2 (-83%)
agents                           3        11  +8 (+267%)
cost split: agents $0.72, rework $0.51, coordinator n/a, total $1.23
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T2 (10.7 min)
model mix: sonnet 3 tasks $1.23
quality: tests 14463 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      5.2     0.5  -4.7 (-90%)     $0.685  first-time miss
T1    sonnet      5.4     1.1  -4.3 (-79%)     $0.247
T2    sonnet      5.3     1.1  -4.2 (-80%)     $0.299

takeaway: ran 42% faster than projected; cost 219% over; biggest miss T3
