# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:46:12

                         Projected    Actual  Delta
wall-clock (min)               6.4      10.4  +4.0 (+63%)
agent cost (USD, +rework)      0.23      0.38  +0.15 (+67%)
task-minutes                   6.4       1.1  -5.3 (-82%)
agents                           2         6  +4 (+200%)
cost split: agents $0.30, rework $0.09, coordinator n/a, total $0.38
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (6.4 min)
model mix: sonnet 2 tasks $0.38
quality: tests 10891 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.1     0.5  -2.6 (-84%)     $0.212  first-time miss
T1    sonnet      3.3     0.6  -2.6 (-80%)     $0.172

takeaway: ran 63% slower than projected; cost 67% over; biggest miss T2
