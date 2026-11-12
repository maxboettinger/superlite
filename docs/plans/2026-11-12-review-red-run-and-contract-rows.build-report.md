# superlite build report

projection: fixed forecast saved at lint 2026-11-12T16:41:47 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.3      14.5  +5.2 (+56%)
agent cost (USD, +rework)      0.34      1.07  +0.73 (+217%)
task-minutes                  41.1       4.0  -37.1 (-90%)
agents                           5        10  +5 (+100%)
cost split: agents $0.88, rework $0.19, coordinator n/a, total $1.07
concurrency: peak 3 at once (projected 5); critical path actual T4; projected T3 (9.3 min)
model mix: sonnet 5 tasks $1.07
quality: tests 7622 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 4/5 (80%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      9.3     1.2  -8.0 (-87%)     $0.297
T5    sonnet      8.2     0.4  -7.8 (-95%)     $0.088
T4    sonnet      7.5     0.4  -7.1 (-94%)     $0.276  first-time miss
T1    sonnet      8.5     1.4  -7.1 (-83%)     $0.293
T2    sonnet      7.6     0.5  -7.1 (-93%)     $0.119

takeaway: ran 56% slower than projected; cost 217% over; biggest miss T3
