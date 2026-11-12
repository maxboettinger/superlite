# superlite build report

projection: fixed forecast saved at lint 2026-11-12T22:49:15 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.3       9.9  +2.6 (+35%)
agent cost (USD, +rework)      0.66      1.34  +0.68 (+104%)
task-minutes                  23.1       5.8  -17.2 (-75%)
agents                           7        10  +3 (+43%)
cost split: agents $1.20, rework $0.14, coordinator n/a, total $1.34
concurrency: peak 3 at once (projected 5); critical path actual T7; projected T1 > T3 (7.3 min)
model mix: sonnet 7 tasks $1.34
quality: tests 8038 passed, 0 failed; first-time pass 4/7 (57%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.0     1.0  -3.1 (-76%)     $0.239
T2    sonnet      3.5     0.7  -2.8 (-80%)     $0.130
T5    sonnet      3.1     0.5  -2.6 (-84%)     $0.134  first-time miss
T6    sonnet      3.1     0.5  -2.6 (-84%)     $0.134  first-time miss
T7    sonnet      3.0     0.7  -2.3 (-77%)     $0.270  first-time miss
(+2 smaller misses; `sl report --json` lists all)

takeaway: ran 35% slower than projected; cost 104% over; biggest miss T1
