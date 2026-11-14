# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:15:40

                         Projected    Actual  Delta
wall-clock (min)               3.6       0.8  -2.8 (-77%)
agent cost (USD, +rework)      0.08      0.15  +0.07 (+81%)
task-minutes                   3.6       0.8  -2.8 (-77%)
agents                           1         3  +2 (+200%)
cost split: agents $0.15, rework $0.00, coordinator n/a, total $0.15
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.6 min)
model mix: sonnet 1 tasks $0.15
quality: tests 9931 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.6     0.8  -2.8 (-77%)     $0.152

takeaway: ran 77% faster than projected; cost 81% over; biggest miss T1
