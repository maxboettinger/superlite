# superlite build report

projection: fixed forecast saved at lint 2026-11-24T17:45:41

                         Projected    Actual  Delta
wall-clock (min)               3.9      14.4  +10.5 (+273%)
agent cost (USD, +rework)      0.14      0.55  +0.41 (+301%)
task-minutes                   3.9       1.5  -2.4 (-61%)
agents                           1         5  +4 (+400%)
cost split: agents $0.35, rework $0.20, coordinator n/a, total $0.55
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.9 min)
model mix: sonnet 1 tasks $0.55
quality: tests 14333 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.9     1.5  -2.4 (-61%)     $0.552  first-time miss

takeaway: ran 273% slower than projected; cost 301% over; biggest miss T1
