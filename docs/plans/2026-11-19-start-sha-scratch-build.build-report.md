# superlite build report

projection: fixed forecast saved at lint 2026-11-19T18:31:03

                         Projected    Actual  Delta
wall-clock (min)              12.5      45.7  +33.2 (+266%)
agent cost (USD, +rework)      0.13      1.11  +0.98 (+778%)
task-minutes                  12.5       3.0  -9.5 (-76%)
agents                           2        13  +11 (+550%)
cost split: agents $0.51, rework $0.60, coordinator n/a, total $1.11
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (12.5 min)
model mix: sonnet 2 tasks $1.11
quality: tests 12948 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 0/2 (0%); rework dispatches 5; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      6.1     0.6  -5.6 (-91%)     $0.279  first-time miss
T1    sonnet      6.3     2.4  -3.9 (-62%)     $0.827  first-time miss

takeaway: ran 266% slower than projected; cost 778% over; biggest miss T2
