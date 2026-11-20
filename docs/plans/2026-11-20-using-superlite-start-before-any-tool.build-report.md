# superlite build report

projection: fixed forecast saved at lint 2026-11-20T18:38:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.1      30.0  +23.9 (+391%)
agent cost (USD, +rework)      0.00      0.21  +0.21 (+7789%)
task-minutes                   6.1       0.3  -5.8 (-95%)
agents                           1         4  +3 (+300%)
cost split: agents $0.09, rework $0.12, coordinator n/a, total $0.21
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.1 min)
model mix: sonnet 1 tasks $0.21
quality: tests 13551 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.1     0.3  -5.8 (-95%)     $0.209  first-time miss

takeaway: ran 391% slower than projected; cost 7789% over; biggest miss T1
