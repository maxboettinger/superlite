# superlite build report

projection: fixed forecast saved at lint 2026-11-09T20:37:09

                         Projected    Actual  Delta
wall-clock (min)               1.3       1.2  -0.1 (-10%)
agent cost (USD, +rework)      0.11      0.51  +0.40 (+380%)
task-minutes                   3.8       1.7  -2.1 (-55%)
agents                           3         5  +2 (+67%)
cost split: agents $0.51, rework $0.00, coordinator n/a, total $0.51
concurrency: peak 2 at once (projected 3); critical path actual T1; projected T2 (1.3 min)
model mix: sonnet 3 tasks $0.51
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.3     0.5  -0.8 (-60%)     $0.209
T3    sonnet      1.3     0.6  -0.7 (-55%)     $0.148
T1    sonnet      1.2     0.6  -0.6 (-49%)     $0.148

takeaway: ran 10% faster than projected; cost 380% over; biggest miss T2
