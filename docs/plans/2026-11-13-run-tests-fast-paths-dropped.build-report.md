# superlite build report

projection: fixed forecast saved at lint 2026-11-13T05:23:29

                         Projected    Actual  Delta
wall-clock (min)              10.0       1.5  -8.5 (-85%)
agent cost (USD, +rework)      0.22      0.30  +0.08 (+37%)
task-minutes                  10.0       1.1  -8.9 (-89%)
agents                           2         4  +2 (+100%)
cost split: agents $0.30, rework $0.00, coordinator n/a, total $0.30
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (10.0 min)
model mix: sonnet 2 tasks $0.30
quality: tests 8948 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      5.4     0.6  -4.8 (-89%)     $0.132
T1    sonnet      4.6     0.5  -4.1 (-88%)     $0.163

takeaway: ran 85% faster than projected; cost 37% over; biggest miss T2
