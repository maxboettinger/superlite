# superlite build report

projection: fixed forecast saved at lint 2026-11-13T06:19:18

                         Projected    Actual  Delta
wall-clock (min)               3.3       0.9  -2.3 (-72%)
agent cost (USD, +rework)      0.14      0.21  +0.07 (+48%)
task-minutes                   3.3       0.9  -2.3 (-72%)
agents                           1         4  +3 (+300%)
cost split: agents $0.21, rework $0.00, coordinator n/a, total $0.21
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.3 min)
model mix: sonnet 1 tasks $0.21
quality: tests 9062 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.3     0.9  -2.3 (-72%)     $0.207

takeaway: ran 72% faster than projected; cost 48% over; biggest miss T1
