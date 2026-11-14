# superlite build report

projection: fixed forecast saved at lint 2026-11-14T12:42:48 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.1       3.4  -12.8 (-79%)
agent cost (USD, +rework)      0.37      1.05  +0.68 (+182%)
task-minutes                  31.3       3.6  -27.7 (-88%)
agents                           4         7  +3 (+75%)
cost split: agents $1.05, rework $0.00, coordinator n/a, total $1.05
concurrency: peak 2 at once (projected 3); critical path actual T2 T4; projected T2 > T4 (16.1 min)
model mix: sonnet 4 tasks $1.05
quality: tests 9749 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      8.4     1.3  -7.2 (-85%)     $0.366
T3    sonnet      7.7     0.7  -7.0 (-92%)     $0.181
T1    sonnet      7.5     0.7  -6.9 (-91%)     $0.181
T4    sonnet      7.7     1.0  -6.6 (-86%)     $0.323

takeaway: ran 79% faster than projected; cost 182% over; biggest miss T2
