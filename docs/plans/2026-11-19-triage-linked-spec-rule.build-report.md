# superlite build report

projection: fixed forecast saved at lint 2026-11-19T12:15:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              13.6      18.0  +4.3 (+32%)
agent cost (USD, +rework)      0.00      0.22  +0.22 (+6369%)
task-minutes                  13.6       0.6  -13.1 (-96%)
agents                           1         4  +3 (+300%)
cost split: agents $0.13, rework $0.09, coordinator n/a, total $0.22
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (13.6 min)
model mix: sonnet 1 tasks $0.22
quality: tests 12239 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     13.6     0.6  -13.1 (-96%)    $0.223  first-time miss

takeaway: ran 32% slower than projected; cost 6369% over; biggest miss T1
