# superlite build report

projection: fixed forecast saved at lint 2026-11-11T09:50:58

                         Projected    Actual  Delta
wall-clock (min)               6.1      74.5  +68.3 (+1115%)
agent cost (USD, +rework)      0.39      2.01  +1.63 (+420%)
task-minutes                   8.4      13.0  +4.6 (+55%)
agents                           4        12  +8 (+200%)
cost split: agents $1.14, rework $0.88, coordinator $6.48 (87 turns, context median 171.6k, peak 365.9k; session $14.17), coordinator per task $1.62 (target $1.00), total $8.49
concurrency: peak 3 at once (projected 2); critical path actual T1; projected T1 > T3 > T4 (6.1 min)
model mix: sonnet 4 tasks $2.01, coordinator opus $6.48
quality: tests 6197 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      2.3     5.2  +2.9 (+129%)    $0.647
T2    sonnet      2.3     3.7  +1.5 (+66%)     $1.016
T3    sonnet      2.3     2.9  +0.7 (+30%)     $0.263
T4    sonnet      1.6     1.2  -0.4 (-26%)     $0.088

takeaway: ran 1115% slower than projected; cost 420% over; biggest miss T1
