# superlite build report

projection: fixed forecast saved at lint 2026-11-20T15:36:51

                         Projected    Actual  Delta
wall-clock (min)               5.2       0.8  -4.4 (-85%)
agent cost (USD, +rework)      0.10      0.18  +0.09 (+88%)
task-minutes                   5.2       0.8  -4.4 (-85%)
agents                           1         4  +3 (+300%)
cost split: agents $0.18, rework $0.00, coordinator n/a, total $0.18
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.2 min)
model mix: sonnet 1 tasks $0.18
quality: tests 13476 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.2     0.8  -4.4 (-85%)     $0.182

takeaway: ran 85% faster than projected; cost 88% over; biggest miss T1
