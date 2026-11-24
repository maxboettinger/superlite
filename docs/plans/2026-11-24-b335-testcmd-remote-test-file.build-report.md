# superlite build report

projection: fixed forecast saved at lint 2026-11-24T18:52:34

                         Projected    Actual  Delta
wall-clock (min)               6.9       1.1  -5.8 (-84%)
agent cost (USD, +rework)      0.16      0.28  +0.12 (+77%)
task-minutes                   6.9       1.1  -5.8 (-84%)
agents                           1         3  +2 (+200%)
cost split: agents $0.28, rework $0.00, coordinator n/a, total $0.28
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.9 min)
model mix: sonnet 1 tasks $0.28
quality: tests 14386 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.9     1.1  -5.8 (-84%)     $0.276

takeaway: ran 84% faster than projected; cost 77% over; biggest miss T1
