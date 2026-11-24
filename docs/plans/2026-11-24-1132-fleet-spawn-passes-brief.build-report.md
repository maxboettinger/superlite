# superlite build report

projection: fixed forecast saved at lint 2026-11-24T16:36:15

                         Projected    Actual  Delta
wall-clock (min)               3.1       8.3  +5.2 (+166%)
agent cost (USD, +rework)      0.06      0.24  +0.18 (+328%)
task-minutes                   9.3       1.6  -7.7 (-83%)
agents                           3         5  +2 (+67%)
cost split: agents $0.15, rework $0.09, coordinator n/a, total $0.24
concurrency: peak 3 at once (projected 3); critical path actual T3; projected T1 (3.1 min)
model mix: haiku 2 tasks $0.12, sonnet 1 tasks $0.12
quality: tests 14231 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.1     0.5  -2.6 (-83%)     $0.124
T2    haiku       3.1     0.5  -2.6 (-83%)     $0.015
T3    haiku       3.1     0.6  -2.5 (-82%)     $0.101  first-time miss

takeaway: ran 166% slower than projected; cost 328% over; biggest miss T1
