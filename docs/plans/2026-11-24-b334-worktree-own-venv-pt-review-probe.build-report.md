# superlite build report

projection: fixed forecast saved at lint 2026-11-24T18:23:49

                         Projected    Actual  Delta
wall-clock (min)               7.0       2.5  -4.5 (-64%)
agent cost (USD, +rework)      0.26      0.39  +0.13 (+52%)
task-minutes                   7.0       2.2  -4.8 (-68%)
agents                           2         3  +1 (+50%)
cost split: agents $0.39, rework $0.00, coordinator n/a, total $0.39
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (7.0 min)
model mix: sonnet 2 tasks $0.39
quality: tests 14369 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.1     0.7  -2.4 (-77%)     $0.127  first-time miss
T1    sonnet      3.9     1.5  -2.4 (-61%)     $0.268

takeaway: ran 64% faster than projected; cost 52% over; biggest miss T2
