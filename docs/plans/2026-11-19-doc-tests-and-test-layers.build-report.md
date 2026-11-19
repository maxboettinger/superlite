# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:37:20

                         Projected    Actual  Delta
wall-clock (min)               9.7       1.3  -8.4 (-86%)
agent cost (USD, +rework)      0.11      0.21  +0.10 (+91%)
task-minutes                  55.2       3.7  -51.4 (-93%)
agents                           6        12  +6 (+100%)
cost split: agents $0.21, rework $0.00, coordinator n/a, total $0.21
concurrency: peak 4 at once (projected 6); critical path actual T6; projected T1 (9.7 min)
model mix: haiku 5 tasks $0.06, sonnet 1 tasks $0.15
quality: tests 12190 passed, 0 failed; first-time pass 6/6 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.7     0.8  -8.9 (-92%)     $0.155
T5    haiku       9.1     0.5  -8.6 (-94%)     $0.011
T4    haiku       9.1     0.6  -8.5 (-94%)     $0.011
T3    haiku       9.1     0.6  -8.5 (-94%)     $0.011
T2    haiku       9.1     0.7  -8.4 (-93%)     $0.013
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 86% faster than projected; cost 91% over; biggest miss T1
