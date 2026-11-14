# superlite build report

projection: fixed forecast saved at lint 2026-11-14T12:51:10 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              19.9      58.9  +39.0 (+196%)
agent cost (USD, +rework)      0.44      4.12  +3.69 (+848%)
task-minutes                  38.7       6.1  -32.6 (-84%)
agents                           4        25  +21 (+525%)
cost split: agents $1.23, rework $2.90, coordinator n/a, total $4.12
concurrency: peak 4 at once (projected 3); critical path actual T2; projected T2 > T3 (19.9 min)
model mix: sonnet 4 tasks $4.12
quality: tests 9884 passed, 0 failed; first-time pass 1/4 (25%); rework dispatches 13; open incidents 2

task  model      pred  actual  delta             cost
T3    sonnet     10.0     1.5  -8.5 (-85%)     $0.346
T4    sonnet      9.6     1.1  -8.5 (-88%)     $0.313  first-time miss
T1    sonnet      9.2     1.1  -8.1 (-88%)     $0.764  first-time miss
T2    sonnet      9.9     2.4  -7.5 (-76%)     $2.701  first-time miss

takeaway: ran 196% slower than projected; cost 848% over; biggest miss T3
