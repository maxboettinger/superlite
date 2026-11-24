# superlite build report

projection: fixed forecast saved at lint 2026-11-24T13:59:27

                         Projected    Actual  Delta
wall-clock (min)              10.0       1.5  -8.5 (-85%)
agent cost (USD, +rework)      0.24      0.28  +0.05 (+20%)
task-minutes                  10.0       1.2  -8.8 (-88%)
agents                           2         6  +4 (+200%)
cost split: agents $0.28, rework $0.00, coordinator n/a, total $0.28
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (10.0 min)
model mix: sonnet 2 tasks $0.28
quality: tests 14016 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      5.2     0.6  -4.6 (-88%)     $0.121
T1    sonnet      4.8     0.6  -4.2 (-87%)     $0.161

takeaway: ran 85% faster than projected; cost 20% over; biggest miss T2
