# superlite build report

projection: fixed forecast saved at lint 2026-11-12T23:03:05 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.8       1.0  -3.8 (-80%)
agent cost (USD, +rework)      0.12      0.24  +0.12 (+100%)
task-minutes                   4.8       1.0  -3.8 (-80%)
agents                           1         3  +2 (+200%)
cost split: agents $0.24, rework $0.00, coordinator n/a, total $0.24
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.8 min)
model mix: sonnet 1 tasks $0.24
quality: tests 8000 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.8     1.0  -3.8 (-80%)     $0.242

takeaway: ran 80% faster than projected; cost 100% over; biggest miss T1
