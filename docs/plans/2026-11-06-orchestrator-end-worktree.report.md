# superlite build report

projection: fixed forecast saved at lint 2026-11-06T12:16:28

                         Projected    Actual  Delta
wall-clock (min)               2.0       1.6  -0.3 (-18%)
agent cost (USD, +rework)      0.11      0.30  +0.19 (+176%)
task-minutes                   2.0       1.6  -0.3 (-18%)
agents                           1         3  +2 (+200%)
cost split: agents $0.30, rework $0.00, coordinator n/a, total $0.30
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (2.0 min)
model mix: sonnet 1 tasks $0.30
quality: tests 21 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.0     1.6  -0.3 (-18%)     $0.299

takeaway: ran 18% faster than projected; cost 176% over; biggest miss T1
