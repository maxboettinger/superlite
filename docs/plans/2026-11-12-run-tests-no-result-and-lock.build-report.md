# superlite build report

projection: fixed forecast saved at lint 2026-11-12T09:32:27 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.9      86.6  +80.7 (+1361%)
agent cost (USD, +rework)      0.96      4.61  +3.64 (+378%)
task-minutes                  22.9      34.9  +12.0 (+52%)
agents                          12        27  +15 (+125%)
cost split: agents $3.11, rework $1.49, coordinator n/a, total $4.61
concurrency: peak 9 at once (projected 7); critical path actual T1; projected T4 > T3 > T12 (5.9 min)
model mix: sonnet 12 tasks $4.61
quality: tests 7178 passed, 0 failed; first-time pass 4/12 (33%); rework dispatches 10; open incidents 4

task  model      pred  actual  delta             cost
T10   sonnet      2.3     9.8  +7.4 (+318%)    $0.738  first-time miss
T11   sonnet      1.6     4.2  +2.6 (+169%)    $0.321  first-time miss
T2    sonnet      1.5     3.7  +2.1 (+142%)    $0.205
T8    sonnet      2.3     3.7  +1.4 (+61%)     $0.553  first-time miss
T6    sonnet      2.3     1.4  -0.9 (-40%)     $0.232
(+7 smaller misses; `sl report --json` lists all)

takeaway: ran 1361% slower than projected; cost 378% over; biggest miss T10
