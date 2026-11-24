# superlite build report

projection: fixed forecast saved at lint 2026-11-24T20:21:07

                         Projected    Actual  Delta
wall-clock (min)               8.3       2.9  -5.3 (-64%)
agent cost (USD, +rework)      0.11      0.30  +0.19 (+168%)
task-minutes                   8.3       2.9  -5.3 (-64%)
agents                           1         5  +4 (+400%)
cost split: agents $0.30, rework $0.00, coordinator n/a, total $0.30
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (8.3 min)
model mix: sonnet 1 tasks $0.30
quality: tests 14427 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      8.3     2.9  -5.3 (-64%)     $0.297

takeaway: ran 64% faster than projected; cost 168% over; biggest miss T1
