# superlite build report

projection: fixed forecast saved at lint 2026-11-15T20:13:10

                         Projected    Actual  Delta
wall-clock (min)               4.0       1.9  -2.0 (-51%)
agent cost (USD, +rework)      0.66      1.45  +0.79 (+121%)
task-minutes                  20.5       7.1  -13.4 (-65%)
agents                           6        11  +5 (+83%)
cost split: agents $1.45, rework $0.00, coordinator n/a, total $1.45
concurrency: peak 6 at once (projected 6); critical path actual T1 T2; projected T1 (4.0 min)
model mix: sonnet 6 tasks $1.45
quality: tests 11194 passed, 0 failed; first-time pass 6/6 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T6    sonnet      3.0     0.4  -2.6 (-86%)     $0.089
T4    sonnet      3.2     0.8  -2.4 (-75%)     $0.185
T3    sonnet      3.2     0.9  -2.3 (-72%)     $0.217
T2    sonnet      3.9     1.7  -2.1 (-55%)     $0.355
T1    sonnet      4.0     1.9  -2.0 (-52%)     $0.434
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 51% faster than projected; cost 121% over; biggest miss T6
