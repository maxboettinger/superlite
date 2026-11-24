# superlite build report

projection: fixed forecast saved at lint 2026-11-24T09:48:51

                         Projected    Actual  Delta
wall-clock (min)              11.4       3.2  -8.3 (-72%)
agent cost (USD, +rework)      0.17      0.63  +0.45 (+261%)
task-minutes                  22.1       3.5  -18.5 (-84%)
agents                           2         5  +3 (+150%)
cost split: agents $0.63, rework $0.00, coordinator n/a, total $0.63
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (11.4 min)
model mix: haiku 1 tasks $0.01, sonnet 1 tasks $0.62
quality: tests 13720 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    haiku      10.6     0.4  -10.2 (-96%)    $0.008
T1    sonnet     11.4     3.2  -8.3 (-72%)     $0.617  first-time miss

takeaway: ran 72% faster than projected; cost 261% over; biggest miss T2
