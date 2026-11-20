# superlite build report

projection: fixed forecast saved at lint 2026-11-20T09:10:38

                         Projected    Actual  Delta
wall-clock (min)               3.3       1.6  -1.7 (-52%)
agent cost (USD, +rework)      0.12      0.22  +0.09 (+77%)
task-minutes                   3.3       1.6  -1.7 (-52%)
agents                           1         3  +2 (+200%)
cost split: agents $0.22, rework $0.00, coordinator n/a, total $0.22
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.3 min)
model mix: sonnet 1 tasks $0.22
quality: tests 13249 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.3     1.6  -1.7 (-52%)     $0.217

takeaway: ran 52% faster than projected; cost 77% over; biggest miss T1
