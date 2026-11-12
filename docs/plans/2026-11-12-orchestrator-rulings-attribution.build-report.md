# superlite build report

projection: fixed forecast saved at lint 2026-11-12T02:47:59

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.9  +0.2 (+15%)
agent cost (USD, +rework)      0.01      0.26  +0.25 (+3865%)
task-minutes                   1.6       0.7  -0.9 (-58%)
agents                           1         4  +3 (+300%)
cost split: agents $0.15, rework $0.10, coordinator n/a, total $0.26
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 1 tasks $0.26
quality: tests 6637 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     0.7  -0.9 (-58%)     $0.256  first-time miss

takeaway: ran 15% slower than projected; cost 3865% over; biggest miss T1
