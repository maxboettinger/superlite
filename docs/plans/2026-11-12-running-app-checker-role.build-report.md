# superlite build report

projection: fixed forecast saved at lint 2026-11-12T14:45:31 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.6       8.3  +3.6 (+79%)
agent cost (USD, +rework)      0.02      0.48  +0.46 (+2512%)
task-minutes                  18.2       2.3  -15.9 (-88%)
agents                           4         6  +2 (+50%)
cost split: agents $0.40, rework $0.07, coordinator n/a, total $0.48
concurrency: peak 4 at once (projected 4); critical path actual T4; projected T3 (4.6 min)
model mix: sonnet 4 tasks $0.48
quality: tests 7327 passed, 0 failed; first-time pass 3/4 (75%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      4.6     0.6  -4.0 (-88%)     $0.175  first-time miss
T3    sonnet      4.6     0.6  -4.0 (-86%)     $0.123
T1    sonnet      4.5     0.6  -4.0 (-88%)     $0.101
T2    sonnet      4.5     0.5  -3.9 (-88%)     $0.079

takeaway: ran 79% slower than projected; cost 2512% over; biggest miss T4
