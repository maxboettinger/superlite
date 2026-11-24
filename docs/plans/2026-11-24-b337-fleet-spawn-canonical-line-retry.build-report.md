# superlite build report

projection: fixed forecast saved at lint 2026-11-24T19:31:00

                         Projected    Actual  Delta
wall-clock (min)              11.3       0.6  -10.7 (-94%)
agent cost (USD, +rework)      0.12      0.18  +0.06 (+46%)
task-minutes                  11.3       0.6  -10.7 (-94%)
agents                           1         3  +2 (+200%)
cost split: agents $0.18, rework $0.00, coordinator n/a, total $0.18
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (11.3 min)
model mix: sonnet 1 tasks $0.18
quality: tests 14411 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     11.3     0.6  -10.7 (-94%)    $0.183

takeaway: ran 94% faster than projected; cost 46% over; biggest miss T1
