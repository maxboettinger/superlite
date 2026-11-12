# superlite build report

projection: fixed forecast saved at lint 2026-11-12T16:40:11 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.6      11.9  +6.3 (+114%)
agent cost (USD, +rework)      0.42      1.34  +0.92 (+216%)
task-minutes                  21.1       5.8  -15.4 (-73%)
agents                           4         9  +5 (+125%)
cost split: agents $1.00, rework $0.34, coordinator n/a, total $1.34
concurrency: peak 3 at once (projected 4); critical path actual T2 T3; projected T3 (5.6 min)
model mix: sonnet 4 tasks $1.34
quality: tests 7632 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      5.5     1.1  -4.4 (-80%)     $0.202
T3    sonnet      5.6     1.5  -4.0 (-73%)     $0.610  first-time miss
T1    sonnet      5.5     1.6  -4.0 (-72%)     $0.310  first-time miss
T4    sonnet      4.6     1.6  -3.0 (-66%)     $0.220

takeaway: ran 114% slower than projected; cost 216% over; biggest miss T2
