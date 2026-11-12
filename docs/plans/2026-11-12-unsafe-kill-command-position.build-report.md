# superlite build report

projection: fixed forecast saved at lint 2026-11-12T23:08:35

                         Projected    Actual  Delta
wall-clock (min)               4.5      16.8  +12.4 (+278%)
agent cost (USD, +rework)      0.24      1.38  +1.14 (+478%)
task-minutes                   4.5      16.8  +12.4 (+278%)
agents                           1         3  +2 (+200%)
cost split: agents $1.38, rework $0.00, coordinator n/a, total $1.38
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.5 min)
model mix: sonnet 1 tasks $1.38
quality: tests 7995 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.5    16.8  +12.4 (+278%)   $1.381

takeaway: ran 278% slower than projected; cost 478% over; biggest miss T1
