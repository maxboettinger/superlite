# superlite build report

projection: fixed forecast saved at lint 2026-11-07T15:25:49

                         Projected    Actual  Delta
wall-clock (min)               1.9       1.4  -0.5 (-27%)
agent cost (USD, +rework)      0.18      0.40  +0.22 (+122%)
task-minutes                   1.9       1.4  -0.5 (-27%)
agents                           1         3  +2 (+200%)
cost split: agents $0.40, rework $0.00, coordinator n/a, total $0.40
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.9 min)
model mix: sonnet 1 tasks $0.40
quality: tests 4007 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.9     1.4  -0.5 (-27%)     $0.400

takeaway: ran 27% faster than projected; cost 122% over; biggest miss T1
