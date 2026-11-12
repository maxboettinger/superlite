# superlite build report

projection: fixed forecast saved at lint 2026-11-12T02:53:33 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.0      34.5  +29.5 (+592%)
agent cost (USD, +rework)      0.57      1.55  +0.98 (+170%)
task-minutes                  11.5       5.6  -5.8 (-51%)
agents                           5        11  +6 (+120%)
cost split: agents $1.31, rework $0.24, coordinator n/a, total $1.55
concurrency: peak 4 at once (projected 3); critical path actual T2; projected T1 > T4 (5.0 min)
model mix: sonnet 5 tasks $1.55
quality: tests 6675 passed, 0 failed; first-time pass 3/5 (60%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      2.5     0.7  -1.7 (-71%)     $0.314  first-time miss
T4    sonnet      2.5     1.2  -1.3 (-53%)     $0.312
T3    sonnet      2.5     1.3  -1.2 (-48%)     $0.321
T5    sonnet      1.6     0.7  -0.8 (-53%)     $0.161
T1    sonnet      2.5     1.8  -0.8 (-30%)     $0.443  first-time miss

takeaway: ran 592% slower than projected; cost 170% over; biggest miss T2
