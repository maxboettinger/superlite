# superlite build report

projection: fixed forecast saved at lint 2026-11-16T13:16:29

                         Projected    Actual  Delta
wall-clock (min)              57.8      69.3  +11.6 (+20%)
agent cost (USD, +rework)      1.90      6.33  +4.44 (+234%)
task-minutes                 172.9      20.3  -152.6 (-88%)
agents                          12        48  +36 (+300%)
cost split: agents $4.40, rework $1.93, coordinator n/a, total $6.33
concurrency: peak 10 at once (projected 7); critical path actual T1 T9; projected T1 > T2 > T4 > T12 (57.8 min)
model mix: sonnet 12 tasks $6.33
quality: tests 11795 passed, 0 failed; first-time pass 4/12 (33%); rework dispatches 15; open incidents 4

task  model      pred  actual  delta             cost
T9    sonnet     14.8     0.8  -14.0 (-95%)    $0.466  first-time miss
T4    sonnet     14.9     1.2  -13.8 (-92%)    $0.330
T11   sonnet     14.1     0.6  -13.5 (-95%)    $0.351  first-time miss
T8    sonnet     14.5     1.2  -13.3 (-92%)    $0.352
T5    sonnet     14.7     1.5  -13.1 (-90%)    $0.523  first-time miss
(+7 smaller misses; `sl report --json` lists all)

takeaway: ran 20% slower than projected; cost 234% over; biggest miss T9
