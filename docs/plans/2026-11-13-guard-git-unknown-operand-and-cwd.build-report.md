# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:53:43 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.1       1.0  -9.2 (-90%)
agent cost (USD, +rework)      0.18      0.21  +0.03 (+19%)
task-minutes                  10.1       1.0  -9.2 (-90%)
agents                           1         3  +2 (+200%)
cost split: agents $0.21, rework $0.00, coordinator n/a, total $0.21
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (10.1 min)
model mix: sonnet 1 tasks $0.21
quality: tests 9265 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     10.1     1.0  -9.2 (-90%)     $0.214

takeaway: ran 90% faster than projected; cost 19% over; biggest miss T1
