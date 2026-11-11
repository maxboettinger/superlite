# superlite build report

projection: fixed forecast saved at lint 2026-11-11T00:02:30 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.8      22.7  +18.9 (+492%)
agent cost (USD, +rework)      0.74      1.59  +0.85 (+114%)
task-minutes                  11.4       6.5  -5.0 (-44%)
agents                           7         8  +1 (+14%)
cost split: agents $1.50, rework $0.09, coordinator n/a, total $1.59
concurrency: peak 5 at once (projected 5); critical path actual T6; projected T1 > T4 (3.8 min)
model mix: sonnet 7 tasks $1.59
quality: tests 5813 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.7     0.7  -1.0 (-58%)     $0.186
T4    sonnet      2.1     1.1  -1.0 (-47%)     $0.278
T3    sonnet      1.4     0.7  -0.8 (-53%)     $0.159
T7    sonnet      1.3     0.6  -0.7 (-54%)     $0.140
T6    sonnet      1.4     0.7  -0.7 (-52%)     $0.245
(+2 smaller misses; `sl report --json` lists all)

takeaway: ran 492% slower than projected; cost 114% over; biggest miss T5
