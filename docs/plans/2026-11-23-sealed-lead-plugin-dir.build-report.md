# superlite build report

projection: fixed forecast saved at lint 2026-11-23T19:28:57

                         Projected    Actual  Delta
wall-clock (min)               4.7       0.9  -3.8 (-81%)
agent cost (USD, +rework)      0.15      0.35  +0.20 (+133%)
task-minutes                   9.5       1.1  -8.3 (-88%)
agents                           2         5  +3 (+150%)
cost split: agents $0.35, rework $0.00, coordinator n/a, total $0.35
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (4.7 min)
model mix: sonnet 2 tasks $0.35
quality: tests 13635 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.7     0.5  -4.2 (-89%)     $0.165
T2    sonnet      4.7     0.6  -4.1 (-87%)     $0.183

takeaway: ran 81% faster than projected; cost 133% over; biggest miss T1
