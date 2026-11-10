# superlite build report

projection: fixed forecast saved at lint 2026-11-10T08:19:08

                         Projected    Actual  Delta
wall-clock (min)               3.2      15.7  +12.5 (+390%)
agent cost (USD, +rework)      0.35      1.19  +0.84 (+237%)
task-minutes                   3.2       4.0  +0.8 (+24%)
agents                           2         6  +4 (+200%)
cost split: agents $0.97, rework $0.22, coordinator n/a, total $1.19
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (3.2 min)
model mix: sonnet 2 tasks $1.19
quality: tests 5265 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.0     2.8  +0.8 (+41%)     $0.675
T2    sonnet      1.2     1.1  -0.1 (-5%)      $0.513

takeaway: ran 390% slower than projected; cost 237% over; biggest miss T1
