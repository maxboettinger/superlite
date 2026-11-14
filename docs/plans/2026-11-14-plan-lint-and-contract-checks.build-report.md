# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:18:41

                         Projected    Actual  Delta
wall-clock (min)              18.9      10.7  -8.2 (-43%)
agent cost (USD, +rework)      0.38      1.11  +0.73 (+193%)
task-minutes                  38.2       4.2  -34.1 (-89%)
agents                           4        15  +11 (+275%)
cost split: agents $0.89, rework $0.22, coordinator n/a, total $1.11
concurrency: peak 3 at once (projected 3); critical path actual T2; projected T2 > T4 (18.9 min)
model mix: sonnet 4 tasks $1.11
quality: tests 9956 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 2/4 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      9.6     0.7  -8.9 (-93%)     $0.159
T2    sonnet      9.7     1.0  -8.7 (-90%)     $0.388  first-time miss
T1    sonnet      9.6     1.0  -8.7 (-90%)     $0.272  first-time miss
T4    sonnet      9.3     1.5  -7.7 (-84%)     $0.296

takeaway: ran 43% faster than projected; cost 193% over; biggest miss T3
