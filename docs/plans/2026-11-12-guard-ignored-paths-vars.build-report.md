# superlite build report

projection: fixed forecast saved at lint 2026-11-12T23:10:28

                         Projected    Actual  Delta
wall-clock (min)              10.9      84.0  +73.1 (+671%)
agent cost (USD, +rework)      0.36      3.49  +3.13 (+862%)
task-minutes                  16.3       5.1  -11.2 (-69%)
agents                           3        25  +22 (+733%)
cost split: agents $1.11, rework $2.39, coordinator $9.44 (129 turns, context median 308.4k, peak 366.5k; session $14.78), coordinator per task $3.15 (target $1.00), total $12.94
concurrency: peak 3 at once (projected 2); critical path actual T1; projected T1 > T3 (10.9 min)
model mix: sonnet 3 tasks $3.49, coordinator opus $9.44
quality: tests 8032 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 11; open incidents 1

task  model      pred  actual  delta             cost
T2    sonnet      5.4     1.4  -4.0 (-74%)     $0.588  first-time miss
T1    sonnet      5.5     1.8  -3.6 (-66%)     $2.525  first-time miss
T3    sonnet      5.4     1.8  -3.6 (-66%)     $0.379

takeaway: ran 671% slower than projected; cost 862% over; biggest miss T2
