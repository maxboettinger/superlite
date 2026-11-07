# superlite build report

projection: fixed forecast saved at lint 2026-11-07T11:20:58

                         Projected    Actual  Delta
wall-clock (min)               1.5       9.6  +8.1 (+536%)
agent cost (USD, +rework)      0.25      1.01  +0.76 (+310%)
task-minutes                   2.9       1.9  -1.1 (-36%)
agents                           2         5  +3 (+150%)
cost split: agents $0.61, rework $0.41, coordinator n/a, total $1.01
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.5 min)
model mix: sonnet 2 tasks $1.01
quality: tests 3961 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.4     0.7  -0.7 (-52%)     $0.399
T2    sonnet      1.5     1.2  -0.3 (-22%)     $0.612

takeaway: ran 536% slower than projected; cost 310% over; biggest miss T1
