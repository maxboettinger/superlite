# superlite build report

projection: fixed forecast saved at lint 2026-11-20T14:49:15

                         Projected    Actual  Delta
wall-clock (min)               9.8       2.7  -7.1 (-72%)
agent cost (USD, +rework)      0.14      0.27  +0.12 (+84%)
task-minutes                   9.8       2.7  -7.1 (-72%)
agents                           1         5  +4 (+400%)
cost split: agents $0.27, rework $0.00, coordinator n/a, total $0.27
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.8 min)
model mix: sonnet 1 tasks $0.27
quality: tests 13460 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.8     2.7  -7.1 (-72%)     $0.266

takeaway: ran 72% faster than projected; cost 84% over; biggest miss T1
