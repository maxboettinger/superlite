# superlite build report

projection: fixed forecast saved at lint 2026-11-20T14:49:53 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              32.4      35.2  +2.8 (+9%)
agent cost (USD, +rework)      0.43      1.21  +0.78 (+180%)
task-minutes                  43.1       5.1  -38.0 (-88%)
agents                           4        11  +7 (+175%)
cost split: agents $0.90, rework $0.32, coordinator n/a, total $1.21
concurrency: peak 3 at once (projected 2); critical path actual T1; projected T1 > T2 > T4 (32.4 min)
model mix: sonnet 4 tasks $1.21
quality: tests 13475 passed, 0 failed; first-time pass 3/4 (75%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     10.8     0.8  -10.0 (-92%)    $0.218
T4    sonnet     10.7     0.7  -10.0 (-93%)    $0.135
T3    sonnet     10.7     0.8  -9.9 (-92%)     $0.156
T1    sonnet     10.9     2.7  -8.2 (-75%)     $0.705  first-time miss

takeaway: ran 9% slower than projected; cost 180% over; biggest miss T2
