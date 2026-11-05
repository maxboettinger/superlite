# superlite build report

projection: fixed forecast saved at lint 2026-11-05T11:27:07 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.7      38.8  +30.1 (+347%)
agent cost (USD, +rework)      0.42      1.34  +0.92 (+217%)
task-minutes                  13.3       7.2  -6.1 (-46%)
agents                           5        12  +7 (+140%)
cost split: agents $0.93, rework $0.42, coordinator $6.07 (83 turns, context median 249.6k, peak 305.7k; session $9.49), total $7.41
concurrency: peak 4 at once (projected 3); critical path actual T5; projected T1 > T2 > T3 (8.7 min)
model mix: sonnet 5 tasks $1.34, coordinator opus $6.07
quality: tests 4 passed, 0 failed; first-time pass 1/5 (20%); rework dispatches 4; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.4     1.1  -2.2 (-67%)     $0.193
T5    sonnet      2.3     0.7  -1.6 (-70%)     $0.307  first-time miss
T4    sonnet      2.3     0.7  -1.6 (-70%)     $0.173  first-time miss
T1    sonnet      2.2     0.8  -1.5 (-65%)     $0.154  first-time miss
T3    sonnet      3.1     3.9  +0.9 (+28%)     $0.518  first-time miss

takeaway: ran 347% slower than projected; cost 217% over; biggest miss T2
