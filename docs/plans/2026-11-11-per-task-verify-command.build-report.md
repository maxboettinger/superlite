# superlite build report

projection: fixed forecast saved at lint 2026-11-11T14:04:51

                         Projected    Actual  Delta
wall-clock (min)               3.3      22.6  +19.3 (+593%)
agent cost (USD, +rework)      0.53      0.92  +0.40 (+75%)
task-minutes                   8.1       4.2  -3.9 (-48%)
agents                           5         7  +2 (+40%)
cost split: agents $0.84, rework $0.09, coordinator n/a, total $0.92
concurrency: peak 3 at once (projected 3); critical path actual T1 T4; projected T1 > T2 (3.3 min)
model mix: sonnet 5 tasks $0.92
quality: tests 6371 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.6     0.4  -1.1 (-72%)     $0.096
T1    sonnet      1.6     0.7  -0.9 (-57%)     $0.136
T4    sonnet      1.6     0.9  -0.7 (-43%)     $0.281
T3    sonnet      1.6     0.9  -0.7 (-42%)     $0.192
T2    sonnet      1.6     1.2  -0.5 (-28%)     $0.220

takeaway: ran 593% slower than projected; cost 75% over; biggest miss T5
