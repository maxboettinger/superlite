# superlite build report

projection: fixed forecast saved at lint 2026-11-10T20:07:02

                         Projected    Actual  Delta
wall-clock (min)               1.5      17.8  +16.4 (+1118%)
agent cost (USD, +rework)      0.38      1.07  +0.69 (+179%)
task-minutes                   5.6       3.0  -2.6 (-46%)
agents                           4         8  +4 (+100%)
cost split: agents $0.81, rework $0.26, coordinator n/a, total $1.07
concurrency: peak 4 at once (projected 4); critical path actual T3; projected T2 (1.5 min)
model mix: sonnet 4 tasks $1.07
quality: tests 5649 passed, 0 failed; first-time pass n/a; rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.4     0.5  -0.9 (-63%)     $0.258
T4    sonnet      1.2     0.5  -0.7 (-57%)     $0.152
T3    sonnet      1.5     0.9  -0.6 (-40%)     $0.326
T2    sonnet      1.5     1.1  -0.4 (-26%)     $0.333

takeaway: ran 1118% slower than projected; cost 179% over; biggest miss T1
