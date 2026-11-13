# superlite build report

projection: fixed forecast saved at lint 2026-11-13T08:28:06

                         Projected    Actual  Delta
wall-clock (min)               4.6       0.9  -3.8 (-81%)
agent cost (USD, +rework)      0.11      0.20  +0.10 (+90%)
task-minutes                   4.6       0.9  -3.8 (-81%)
agents                           1         3  +2 (+200%)
cost split: agents $0.20, rework $0.00, coordinator n/a, total $0.20
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.6 min)
model mix: sonnet 1 tasks $0.20
quality: tests 9334 passed, 0 failed (last full run; newer fast run: 292 passed, 0 failed); first-time pass 0/1 (0%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.6     0.9  -3.8 (-81%)     $0.202  first-time miss

takeaway: ran 81% faster than projected; cost 90% over; biggest miss T1
