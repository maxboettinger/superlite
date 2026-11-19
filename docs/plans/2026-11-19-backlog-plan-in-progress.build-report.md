# superlite build report

projection: fixed forecast saved at lint 2026-11-19T10:00:44 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.6      13.3  -3.3 (-20%)
agent cost (USD, +rework)      0.30      0.71  +0.41 (+136%)
task-minutes                  24.3       3.1  -21.2 (-87%)
agents                           3         7  +4 (+133%)
cost split: agents $0.55, rework $0.17, coordinator n/a, total $0.71
concurrency: peak 2 at once (projected 2); critical path actual DOC1; projected IP1 > IP2 (16.6 min)
model mix: haiku 1 tasks $0.18, sonnet 2 tasks $0.53
quality: tests 12057 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 7

task  model      pred  actual  delta             cost
DOC1  haiku       7.6     0.6  -7.1 (-93%)     $0.182  first-time miss
IP1   sonnet      8.3     1.2  -7.1 (-85%)     $0.234
IP2   sonnet      8.3     1.3  -7.0 (-84%)     $0.299

takeaway: ran 20% faster than projected; cost 136% over; biggest miss DOC1
