# superlite build report

projection: fixed forecast saved at lint 2026-11-07T17:14:18

                         Projected    Actual  Delta
wall-clock (min)               2.5       3.0  +0.5 (+21%)
agent cost (USD, +rework)      0.21      0.81  +0.60 (+281%)
task-minutes                   3.5       1.7  -1.8 (-52%)
agents                           3         5  +2 (+67%)
cost split: agents $0.65, rework $0.17, coordinator n/a, total $0.81
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 > T3 (2.5 min)
model mix: sonnet 3 tasks $0.81
quality: tests 4113 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.2     0.5  -0.7 (-57%)     $0.202
T2    sonnet      1.0     0.4  -0.6 (-59%)     $0.176
T1    sonnet      1.3     0.8  -0.6 (-41%)     $0.436

takeaway: ran 21% slower than projected; cost 281% over; biggest miss T3
