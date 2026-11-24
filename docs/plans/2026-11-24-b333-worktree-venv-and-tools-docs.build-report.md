# superlite build report

projection: fixed forecast saved at lint 2026-11-24T17:49:11

                         Projected    Actual  Delta
wall-clock (min)               7.0       5.5  -1.6 (-22%)
agent cost (USD, +rework)      0.25      0.58  +0.33 (+133%)
task-minutes                   7.0       2.0  -5.1 (-72%)
agents                           2         4  +2 (+100%)
cost split: agents $0.46, rework $0.12, coordinator n/a, total $0.58
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (7.0 min)
model mix: sonnet 2 tasks $0.58
quality: tests 14311 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.9     0.9  -2.9 (-76%)     $0.255
T2    sonnet      3.2     1.1  -2.1 (-67%)     $0.325  first-time miss

takeaway: ran 22% faster than projected; cost 133% over; biggest miss T1
