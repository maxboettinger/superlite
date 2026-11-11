# superlite build report

projection: fixed forecast saved at lint 2026-11-11T01:50:57

                         Projected    Actual  Delta
wall-clock (min)               4.0      26.1  +22.1 (+559%)
agent cost (USD, +rework)      0.47      1.20  +0.73 (+153%)
task-minutes                   8.5       4.2  -4.3 (-50%)
agents                           5         8  +3 (+60%)
cost split: agents $1.00, rework $0.20, coordinator n/a, total $1.20
concurrency: peak 3 at once (projected 4); critical path actual T5; projected T1 > T2 (4.0 min)
model mix: sonnet 5 tasks $1.20
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.4     0.4  -1.0 (-73%)     $0.090
T5    sonnet      1.4     0.4  -1.0 (-73%)     $0.187
T2    sonnet      2.2     1.4  -0.8 (-37%)     $0.369
T1    sonnet      1.8     1.0  -0.8 (-44%)     $0.314
T4    sonnet      1.8     1.2  -0.7 (-36%)     $0.243

takeaway: ran 559% slower than projected; cost 153% over; biggest miss T3
