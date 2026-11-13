# superlite build report

projection: fixed forecast saved at lint 2026-11-13T01:25:52 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.1       9.6  +5.5 (+133%)
agent cost (USD, +rework)      0.36      1.26  +0.90 (+252%)
task-minutes                  11.2       4.9  -6.3 (-57%)
agents                           3         7  +4 (+133%)
cost split: agents $1.09, rework $0.17, coordinator n/a, total $1.26
concurrency: peak 3 at once (projected 3); critical path actual T3; projected T2 (4.1 min)
model mix: sonnet 3 tasks $1.26
quality: tests 8478 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.0     1.4  -2.7 (-66%)     $0.316
T2    sonnet      4.1     1.6  -2.5 (-61%)     $0.364
T3    sonnet      3.0     1.9  -1.2 (-38%)     $0.578  first-time miss

takeaway: ran 133% slower than projected; cost 252% over; biggest miss T1
