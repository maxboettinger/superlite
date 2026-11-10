# superlite build report

projection: fixed forecast saved at lint 2026-11-10T10:56:04

                         Projected    Actual  Delta
wall-clock (min)               1.7      13.9  +12.2 (+725%)
agent cost (USD, +rework)      0.49      1.07  +0.58 (+118%)
task-minutes                   4.7       3.2  -1.6 (-33%)
agents                           3         5  +2 (+67%)
cost split: agents $0.86, rework $0.21, coordinator n/a, total $1.07
concurrency: peak 2 at once (projected 3); critical path actual T2; projected T1 (1.7 min)
model mix: sonnet 3 tasks $1.07
quality: tests 5420 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.6     0.7  -0.9 (-54%)     $0.247
T2    sonnet      1.4     0.7  -0.7 (-48%)     $0.455
T1    sonnet      1.7     1.7  +0.0 (+0%)      $0.366

takeaway: ran 725% slower than projected; cost 118% over; biggest miss T3
