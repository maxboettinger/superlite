# superlite build report

projection: fixed forecast saved at lint 2026-11-24T14:58:27

                         Projected    Actual  Delta
wall-clock (min)               5.3       1.0  -4.3 (-81%)
agent cost (USD, +rework)      0.13      0.20  +0.07 (+55%)
task-minutes                   5.3       1.0  -4.3 (-81%)
agents                           1         4  +3 (+300%)
cost split: agents $0.20, rework $0.00, coordinator n/a, total $0.20
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.3 min)
model mix: sonnet 1 tasks $0.20
quality: tests 14083 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.3     1.0  -4.3 (-81%)     $0.198

takeaway: ran 81% faster than projected; cost 55% over; biggest miss T1
