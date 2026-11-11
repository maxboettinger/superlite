# superlite build report

projection: fixed forecast saved at lint 2026-11-11T02:12:24 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.2      34.3  +31.1 (+974%)
agent cost (USD, +rework)      0.90      3.07  +2.17 (+241%)
task-minutes                  19.0      33.5  +14.5 (+76%)
agents                          12        16  +4 (+33%)
cost split: agents $2.97, rework $0.10, coordinator $6.74 (92 turns, context median 281.8k, peak 327.4k; session $11.26), coordinator per task $0.45 (target $1.00), total $9.81
concurrency: peak 8 at once (projected 10); critical path actual T7 T14; projected T1 > T2 (3.2 min)
model mix: sonnet 15 tasks $3.07, coordinator opus $6.74
quality: tests 4 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.8     5.9  +4.1 (+232%)    $0.572
T7    sonnet      1.4     2.7  +1.3 (+96%)     $0.130
T11   sonnet      1.8     2.9  +1.1 (+64%)     $0.247
T8    sonnet      1.4     2.5  +1.1 (+79%)     $0.246
T10   sonnet      1.4     2.5  +1.1 (+76%)     $0.144
(+10 smaller misses; `sl report --json` lists all)

takeaway: ran 974% slower than projected; cost 241% over; biggest miss T1
