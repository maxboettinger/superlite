# superlite build report

projection: fixed forecast saved at lint 2026-11-12T06:24:49 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.4      21.6  +19.2 (+805%)
agent cost (USD, +rework)      0.58      1.52  +0.94 (+162%)
task-minutes                  13.3       8.0  -5.3 (-40%)
agents                           7         9  +2 (+29%)
cost split: agents $1.24, rework $0.28, coordinator n/a, total $1.52
concurrency: peak 5 at once (projected 7); critical path actual T7; projected T5 (2.4 min)
model mix: sonnet 7 tasks $1.52
quality: tests 7022 passed, 0 failed; first-time pass 6/7 (85%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T6    sonnet      2.3     0.9  -1.4 (-61%)     $0.137
T5    sonnet      2.4     1.5  -0.9 (-37%)     $0.239
T7    sonnet      1.5     0.7  -0.8 (-53%)     $0.399  first-time miss
T3    sonnet      1.6     0.9  -0.7 (-45%)     $0.137
T1    sonnet      1.9     1.2  -0.7 (-35%)     $0.165
(+2 smaller misses; `sl report --json` lists all)

takeaway: ran 805% slower than projected; cost 162% over; biggest miss T6
