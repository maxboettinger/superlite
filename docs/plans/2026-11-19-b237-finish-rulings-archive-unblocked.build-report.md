# superlite build report

projection: fixed forecast saved at lint 2026-11-19T10:12:28

                         Projected    Actual  Delta
wall-clock (min)              24.4      23.4  -1.0 (-4%)
agent cost (USD, +rework)      0.66      2.30  +1.64 (+249%)
task-minutes                  87.7       9.6  -78.1 (-89%)
agents                          11        34  +23 (+209%)
cost split: agents $1.90, rework $0.40, coordinator n/a, total $2.30
concurrency: peak 7 at once (projected 8); critical path actual T5; projected T1 > T2 > T11 (24.4 min)
model mix: haiku 1 tasks $0.01, sonnet 10 tasks $2.29
quality: tests 12107 passed, 0 failed; first-time pass 7/11 (63%); rework dispatches 4; open incidents 10

task  model      pred  actual  delta             cost
T4    sonnet      8.5     0.9  -7.5 (-89%)     $0.245
T7    sonnet      8.1     0.6  -7.5 (-93%)     $0.241  first-time miss
T3    sonnet      8.1     0.8  -7.3 (-90%)     $0.188
T5    sonnet      8.1     0.9  -7.2 (-89%)     $0.296  first-time miss
T1    sonnet      8.2     1.0  -7.2 (-88%)     $0.284  first-time miss
(+6 smaller misses; `sl report --json` lists all)

takeaway: ran 4% faster than projected; cost 249% over; biggest miss T4
